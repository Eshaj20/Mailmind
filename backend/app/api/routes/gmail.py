from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_gmail_client, get_llm_client, get_sync_queue
from app.core.config import settings
from app.models.gmail import Email, EmailThread, GmailAccount
from app.models.sync_job import SyncJob
from app.models.user import User
from app.schemas.gmail import (
    ClassificationBatchRead,
    ClassificationSummaryRead,
    CleanupSuggestionRead,
    EmailRead,
    EmailSearchResponse,
    EmailSearchResultRead,
    GmailAccountRead,
    GmailOAuthCallback,
    GmailOAuthUrl,
    GmailSyncResult,
    InboxHealthRead,
    SyncJobRead,
    ThreadRead,
)
from app.services.classification import LLMClient, classify_unclassified_emails, summarize_thread
from app.services.gmail import (
    GmailClient,
    create_oauth_state,
    parse_oauth_state,
    sync_latest_messages,
    upsert_gmail_account,
)
from app.services.intelligence import build_inbox_health
from app.services.search import hybrid_search_emails
from app.services.sync_jobs import create_sync_job
from app.services.sync_queue import SyncJobQueue

router = APIRouter()

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
    account_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    queue: SyncJobQueue = Depends(get_sync_queue),
) -> SyncJob:
    query = select(GmailAccount).where(GmailAccount.user_id == current_user.id)
    if account_id is not None:
        query = query.where(GmailAccount.id == account_id)
    account = db.scalar(query)
    if account is None:
        raise HTTPException(status_code=404, detail="Gmail account not connected")

    job = create_sync_job(db, current_user, account)
    db.commit()
    db.refresh(job)
    celery_task_id = queue.enqueue(job.id)
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


@router.get("/emails", response_model=list[EmailRead])
def list_emails(
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Email]:
    return list(
        db.scalars(
            select(Email)
            .where(Email.user_id == current_user.id)
            .order_by(desc(Email.received_at), desc(Email.id))
            .limit(limit)
        )
    )

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
        cleanup_candidate_count=health.cleanup_candidate_count,
        formula=health.formula,
        suggestions=[CleanupSuggestionRead(**suggestion.__dict__) for suggestion in health.suggestions],
    )


@router.post("/classify", response_model=ClassificationBatchRead)
def classify_emails(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> ClassificationBatchRead:
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










