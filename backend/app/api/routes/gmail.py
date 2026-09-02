from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_gmail_client, get_llm_client, get_sync_queue
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.models.gmail import Email, EmailThread, GmailAccount
from app.models.sync_job import SyncJob
from app.models.user import User
from app.schemas.gmail import (
    AIUsageSummaryRead,
    ClassificationBatchRead,
    ClassificationSummaryRead,
    CleanupActionRequest,
    CleanupActionResultRead,
    CleanupUndoResultRead,
    CleanupPreviewItemRead,
    CleanupPreviewRead,
    CleanupSuggestionRead,
    EmailFeedbackCreate,
    EmailFeedbackRead,
    EmailPageRead,
    EmailRead,
    EmailSearchResponse,
    EmailSearchResultRead,
    EvaluationReportRead,
    GmailAccountRead,
    GmailOAuthCallback,
    GmailOAuthUrl,
    GmailSyncResult,
    InboxHealthRead,
    SenderBreakdownRead,
    SenderInsightRead,
    SyncHealthRead,
    SyncJobRead,
    ThreadRead,
)
from app.services.classification import LLMClient, classify_unclassified_emails, summarize_thread
from app.services.cleanup_actions import apply_cleanup_action, undo_cleanup_action
from app.services.feedback import record_email_feedback
from app.services.gmail import (
    GmailClient,
    GmailSyncError,
    PermanentGmailSyncError,
    TransientGmailSyncError,
    create_oauth_state,
    parse_oauth_state,
    sync_latest_messages,
    upsert_gmail_account,
)
from app.services.intelligence import build_cleanup_preview, build_inbox_health, build_sender_intelligence
from app.services.search import hybrid_search_emails
from app.services.sync_jobs import create_sync_job
from app.services.sync_queue import SyncJobQueue, SyncQueueUnavailableError
from app.services.usage import build_ai_usage_summary

router = APIRouter()
EVALUATION_REPORT_PATH = Path(__file__).resolve().parents[3] / "eval" / "eval_report.md"


def _enforce_expensive_action_limit(request: Request) -> None:
    enforce_rate_limit(request, limit=settings.api_rate_limit_per_minute)


# Fail fast when local/dev env does not have Google OAuth credentials configured.
def _ensure_google_configured() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )


@router.get("/oauth/authorize", response_model=GmailOAuthUrl)
def oauth_authorize(
    current_user: User = Depends(get_current_user),
    client: GmailClient = Depends(get_gmail_client),
) -> GmailOAuthUrl:
    _ensure_google_configured()
    state = create_oauth_state(current_user.id)
    return GmailOAuthUrl(authorization_url=client.authorization_url(state))


# GET supports Google's browser redirect; POST keeps the same flow easy to test from API clients.
@router.get("/oauth/callback", response_model=GmailSyncResult)
def oauth_callback_get(
    code: str = Query(min_length=1),
    state: str = Query(min_length=1),
    db: Session = Depends(get_db),
    client: GmailClient = Depends(get_gmail_client),
) -> GmailSyncResult:
    return _handle_oauth_callback(code=code, state=state, db=db, client=client)


@router.post("/oauth/callback", response_model=GmailSyncResult)
def oauth_callback_post(
    payload: GmailOAuthCallback,
    db: Session = Depends(get_db),
    client: GmailClient = Depends(get_gmail_client),
) -> GmailSyncResult:
    return _handle_oauth_callback(code=payload.code, state=payload.state, db=db, client=client)


@router.get("/accounts", response_model=list[GmailAccountRead])
def list_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GmailAccount]:
    return list(db.scalars(select(GmailAccount).where(GmailAccount.user_id == current_user.id)))


@router.post("/sync", response_model=SyncJobRead, status_code=status.HTTP_202_ACCEPTED)
def queue_sync(
    request: Request,
    account_id: int | None = None,
    max_results: int | None = Query(default=None, ge=1, le=12000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    queue: SyncJobQueue = Depends(get_sync_queue),
) -> SyncJob:
    _enforce_expensive_action_limit(request)
    query = select(GmailAccount).where(GmailAccount.user_id == current_user.id)
    if account_id is not None:
        query = query.where(GmailAccount.id == account_id)
    account = db.scalar(query)
    if account is None:
        raise HTTPException(status_code=404, detail="Gmail account not connected")

    job = create_sync_job(db, current_user, account, max_results=max_results)
    db.commit()
    db.refresh(job)
    try:
        celery_task_id = queue.enqueue(job.id)
    except SyncQueueUnavailableError as exc:
        job.status = "failed"
        job.error_type = "queue_unavailable"
        job.error_message = str(exc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail sync worker queue is unavailable",
        ) from exc
    if celery_task_id:
        job.celery_task_id = celery_task_id
        db.commit()
        db.refresh(job)
    return job


@router.get("/sync/jobs", response_model=list[SyncJobRead])
def list_sync_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SyncJob]:
    return list(
        db.scalars(
            select(SyncJob)
            .where(SyncJob.user_id == current_user.id)
            .order_by(desc(SyncJob.created_at), desc(SyncJob.id))
        )
    )



@router.get("/sync/health", response_model=SyncHealthRead)
def get_sync_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncHealthRead:
    jobs = list(db.scalars(select(SyncJob).where(SyncJob.user_id == current_user.id)))
    status_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    for job in jobs:
        status_counts[job.status] = status_counts.get(job.status, 0) + 1
        if job.error_type:
            error_counts[job.error_type] = error_counts.get(job.error_type, 0) + 1

    latest = max(jobs, key=lambda job: job.created_at, default=None)
    last_success = max((job.finished_at for job in jobs if job.status == "succeeded" and job.finished_at), default=None)
    avg_synced_count = round(sum(job.synced_count for job in jobs) / len(jobs), 2) if jobs else 0.0
    return SyncHealthRead(
        total_jobs=len(jobs),
        queued_jobs=status_counts.get("queued", 0),
        running_jobs=status_counts.get("running", 0),
        retrying_jobs=status_counts.get("retrying", 0),
        succeeded_jobs=status_counts.get("succeeded", 0),
        failed_jobs=status_counts.get("failed", 0),
        latest_status=latest.status if latest else None,
        last_sync_at=last_success,
        avg_synced_count=avg_synced_count,
        error_counts=error_counts,
    )
@router.get("/sync/jobs/{job_id}", response_model=SyncJobRead)
def get_sync_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncJob:
    job = db.scalar(select(SyncJob).where(SyncJob.id == job_id, SyncJob.user_id == current_user.id))
    if job is None:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return job


@router.get("/emails", response_model=EmailPageRead)
def list_emails(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    is_read: bool | None = Query(default=None),
    needs_reply: bool | None = Query(default=None),
    sender: str | None = Query(default=None, max_length=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailPageRead:
    query = select(Email).where(Email.user_id == current_user.id)
    count_query = select(func.count(Email.id)).where(Email.user_id == current_user.id)

    filters = []
    if category:
        filters.append(Email.category == category)
    if priority:
        filters.append(Email.priority == priority)
    if is_read is not None:
        filters.append(Email.is_read == is_read)
    if needs_reply is not None:
        filters.append(Email.needs_reply == needs_reply)
    if sender:
        filters.append(Email.sender.ilike(f"%{sender}%"))

    for condition in filters:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = int(db.scalar(count_query) or 0)
    items = list(
        db.scalars(
            query.order_by(desc(Email.received_at), desc(Email.id))
            .offset(offset)
            .limit(limit)
        )
    )
    return EmailPageRead(items=items, total=total, limit=limit, offset=offset, has_more=offset + len(items) < total)


# Hybrid search combines Postgres full-text results and pgvector semantic results.
@router.get("/search", response_model=EmailSearchResponse)
def search_emails(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=10, ge=1, le=25),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailSearchResponse:
    results = hybrid_search_emails(db=db, user=current_user, query=q, limit=limit)
    return EmailSearchResponse(
        query=q,
        results=[
            EmailSearchResultRead(
                email=result.email,
                keyword_rank=result.keyword_rank,
                vector_rank=result.vector_rank,
                keyword_score=result.keyword_score,
                vector_score=result.vector_score,
                rrf_score=result.rrf_score,
                match_reason=result.match_reason,
            )
            for result in results
        ],
    )


@router.get("/insights", response_model=InboxHealthRead)
def get_inbox_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InboxHealthRead:
    health = build_inbox_health(db=db, user=current_user)
    return InboxHealthRead(
        score=health.score,
        total_emails=health.total_emails,
        unread_count=health.unread_count,
        high_priority_unread_count=health.high_priority_unread_count,
        pending_reply_count=health.pending_reply_count,
        aged_follow_up_count=health.aged_follow_up_count,
        oldest_follow_up_days=health.oldest_follow_up_days,
        follow_up_age_days=health.follow_up_age_days,
        cleanup_candidate_count=health.cleanup_candidate_count,
        formula=health.formula,
        suggestions=[
            CleanupSuggestionRead(
                suggestion_type=suggestion.suggestion_type,
                title=suggestion.title,
                description=suggestion.description,
                email_count=suggestion.email_count,
                estimated_time_saved_minutes=suggestion.estimated_time_saved_minutes,
                confidence=suggestion.confidence,
                candidate_emails=suggestion.candidate_emails,
                sender_breakdown=[SenderBreakdownRead(**sender.__dict__) for sender in suggestion.sender_breakdown],
                oldest_days_pending=suggestion.oldest_days_pending,
            )
            for suggestion in health.suggestions
        ],
    )


@router.get("/cleanup/preview", response_model=CleanupPreviewRead)
def get_cleanup_preview(
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CleanupPreviewRead:
    preview = build_cleanup_preview(db=db, user=current_user, limit=limit)
    return CleanupPreviewRead(
        total_candidates=preview.total_candidates,
        estimated_time_saved_minutes=preview.estimated_time_saved_minutes,
        items=[
            CleanupPreviewItemRead(
                email=item.email,
                reason=item.reason,
                suggested_action=item.suggested_action,
                confidence=item.confidence,
            )
            for item in preview.items
        ],
    )


@router.post("/cleanup/actions", response_model=CleanupActionResultRead)
def apply_cleanup_action_endpoint(
    payload: CleanupActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: GmailClient = Depends(get_gmail_client),
) -> CleanupActionResultRead:
    _enforce_expensive_action_limit(request)
    try:
        result = apply_cleanup_action(
            db=db,
            user=current_user,
            client=client,
            email_ids=payload.email_ids,
            action=payload.action,
        )
    except GmailSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    db.commit()
    return CleanupActionResultRead(
        action=result.action,
        requested_count=result.requested_count,
        applied_count=result.applied_count,
        skipped_count=result.skipped_count,
        action_ids=result.action_ids,
        emails=result.emails,
    )



@router.post("/cleanup/actions/{action_id}/undo", response_model=CleanupUndoResultRead)
def undo_cleanup_action_endpoint(
    action_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: GmailClient = Depends(get_gmail_client),
) -> CleanupUndoResultRead:
    _enforce_expensive_action_limit(request)
    try:
        result = undo_cleanup_action(db=db, user=current_user, client=client, action_id=action_id)
    except GmailSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Cleanup action not found or already undone")

    db.commit()
    db.refresh(result.email)
    return CleanupUndoResultRead(
        action_id=result.action_id,
        action=result.action,
        email=result.email,
        restored_labels=result.restored_labels,
        restored_is_read=result.restored_is_read,
    )
@router.get("/senders", response_model=list[SenderInsightRead])
def list_sender_insights(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SenderInsightRead]:
    insights = build_sender_intelligence(db=db, user=current_user, limit=limit)
    return [
        SenderInsightRead(
            sender=insight.sender,
            total_emails=insight.total_emails,
            unread_count=insight.unread_count,
            cleanup_candidate_count=insight.cleanup_candidate_count,
            pending_reply_count=insight.pending_reply_count,
            last_seen_at=insight.last_seen_at,
            suggested_action=insight.suggested_action,
            confidence=insight.confidence,
            candidate_emails=insight.candidate_emails,
        )
        for insight in insights
    ]


@router.post("/feedback", response_model=EmailFeedbackRead, status_code=status.HTTP_201_CREATED)
def create_email_feedback(
    payload: EmailFeedbackCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailFeedbackRead:
    _enforce_expensive_action_limit(request)
    result = record_email_feedback(
        db=db,
        user=current_user,
        email_id=payload.email_id,
        feedback_type=payload.feedback_type,
        corrected_category=payload.corrected_category,
        corrected_priority=payload.corrected_priority,
        corrected_needs_reply=payload.corrected_needs_reply,
        note=payload.note,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Email not found")

    db.commit()
    db.refresh(result.feedback)
    return result.feedback


@router.post("/classify", response_model=ClassificationBatchRead)
def classify_emails(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> ClassificationBatchRead:
    _enforce_expensive_action_limit(request)
    stats = classify_unclassified_emails(db, current_user, llm_client=llm_client)
    return ClassificationBatchRead(
        classified_count=stats.classified_count,
        by_category=stats.by_category or {},
        by_priority=stats.by_priority or {},
        needs_reply_count=stats.needs_reply_count,
        stage_counts=stats.stage_counts or {},
    )


@router.get("/classification/summary", response_model=ClassificationSummaryRead)
def classification_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassificationSummaryRead:
    classified = list(
        db.scalars(select(Email).where(Email.user_id == current_user.id, Email.classified_at.isnot(None)))
    )
    unclassified_total = len(
        list(db.scalars(select(Email.id).where(Email.user_id == current_user.id, Email.classified_at.is_(None))))
    )

    by_category: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    needs_reply_count = 0
    for email in classified:
        if email.category:
            by_category[email.category] = by_category.get(email.category, 0) + 1
        if email.priority:
            by_priority[email.priority] = by_priority.get(email.priority, 0) + 1
        if email.needs_reply:
            needs_reply_count += 1

    return ClassificationSummaryRead(
        total_classified=len(classified),
        total_unclassified=unclassified_total,
        by_category=by_category,
        by_priority=by_priority,
        needs_reply_count=needs_reply_count,
    )



@router.get("/ai/usage", response_model=AIUsageSummaryRead)
def get_ai_usage_summary(
    since_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIUsageSummaryRead:
    summary = build_ai_usage_summary(db=db, user=current_user, since_days=since_days)
    return AIUsageSummaryRead(**summary.__dict__)
@router.get("/classification/evaluation", response_model=EvaluationReportRead)
def get_classification_evaluation(
    current_user: User = Depends(get_current_user),
) -> EvaluationReportRead:
    if not EVALUATION_REPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="Evaluation report not generated yet")
    return EvaluationReportRead(report_markdown=EVALUATION_REPORT_PATH.read_text(encoding="utf-8"))


@router.get("/threads", response_model=list[ThreadRead])
def list_threads(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EmailThread]:
    return list(
        db.scalars(
            select(EmailThread)
            .where(EmailThread.user_id == current_user.id)
            .order_by(desc(EmailThread.last_message_at), desc(EmailThread.id))
            .limit(limit)
        )
    )


@router.post("/threads/{thread_id}/summarize", response_model=ThreadRead)
def summarize_thread_endpoint(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> EmailThread:
    thread = db.scalar(
        select(EmailThread).where(EmailThread.id == thread_id, EmailThread.user_id == current_user.id)
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    summarize_thread(db, thread, llm_client=llm_client)
    db.commit()
    db.refresh(thread)
    return thread



def _gmail_error_status(exc: GmailSyncError) -> int:
    if isinstance(exc, TransientGmailSyncError):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    if isinstance(exc, PermanentGmailSyncError):
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_502_BAD_GATEWAY
def _handle_oauth_callback(
    code: str,
    state: str,
    db: Session,
    client: GmailClient,
) -> GmailSyncResult:
    try:
        user_id = parse_oauth_state(state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid OAuth state") from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="OAuth user not found")

    token_response = client.exchange_code(code)
    access_token = token_response.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Google did not return an access token")

    profile = client.fetch_profile(access_token)
    google_email = profile.get("emailAddress")
    if not google_email:
        raise HTTPException(status_code=502, detail="Google profile did not include an email address")

    existing_account = db.scalar(
        select(GmailAccount).where(
            GmailAccount.user_id == user.id,
            GmailAccount.google_email == google_email,
        )
    )
    refresh_token = token_response.get("refresh_token")
    if not refresh_token and existing_account is None:
        raise HTTPException(status_code=400, detail="Google did not return a refresh token")

    account = upsert_gmail_account(
        db=db,
        user=user,
        google_email=google_email,
        refresh_token=refresh_token,
        scopes=str(token_response.get("scope", "")).split() or settings.gmail_scope_list,
        history_id=str(profile.get("historyId")) if profile.get("historyId") else None,
    )
    db.flush()

    messages = client.fetch_latest_messages(
        access_token,
        max_results=settings.gmail_initial_sync_max_results,
    )
    stats = sync_latest_messages(db=db, user=user, account=account, messages=messages)
    db.commit()
    db.refresh(account)
    return GmailSyncResult(account=account, **stats.__dict__)
