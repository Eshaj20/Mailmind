from datetime import UTC, datetime
import logging
import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.gmail import GmailAccount
from app.models.sync_job import SyncJob
from app.models.user import User
from app.services.gmail import (
    GmailClient,
    GmailSyncStats,
    PermanentGmailSyncError,
    TransientGmailSyncError,
    sync_gmail_account,
)

logger = logging.getLogger(__name__)

SYNC_STATUS_QUEUED = "queued"
SYNC_STATUS_RUNNING = "running"
SYNC_STATUS_RETRYING = "retrying"
SYNC_STATUS_SUCCEEDED = "succeeded"
SYNC_STATUS_FAILED = "failed"


def create_sync_job(db: Session, user: User, account: GmailAccount) -> SyncJob:
    job = SyncJob(
        user_id=user.id,
        gmail_account_id=account.id,
        job_type="gmail_sync",
        status=SYNC_STATUS_QUEUED,
        max_attempts=settings.sync_job_max_attempts,
    )
    db.add(job)
    db.flush()
    return job


def process_sync_job(
    db: Session,
    sync_job_id: int,
    client: GmailClient | None = None,
    raise_for_retry: bool = False,
) -> SyncJob:
    job = db.get(SyncJob, sync_job_id)
    if job is None:
        raise ValueError(f"Sync job {sync_job_id} was not found")

    account = db.get(GmailAccount, job.gmail_account_id)
    user = db.get(User, job.user_id)
    if account is None or user is None:
        job.status = SYNC_STATUS_FAILED
        job.error_type = "missing_sync_target"
        job.error_message = "Gmail account or user no longer exists"
        job.finished_at = datetime.now(UTC)
        db.commit()
        return job

    started = time.perf_counter()
    job.status = SYNC_STATUS_RUNNING
    job.attempt_count += 1
    job.started_at = job.started_at or datetime.now(UTC)
    job.error_type = None
    job.error_message = None
    logger.info(
        "sync.started",
        extra={
            "sync_job_id": job.id,
            "user_id": job.user_id,
            "gmail_account_id": job.gmail_account_id,
            "attempt_count": job.attempt_count,
        },
    )

    try:
        stats = sync_gmail_account(
            db=db,
            user=user,
            account=account,
            client=client or GmailClient(),
            max_results=settings.gmail_initial_sync_max_results,
        )
    except TransientGmailSyncError as exc:
        _mark_transient_failure(db, job, exc, started)
        if raise_for_retry and job.status == SYNC_STATUS_RETRYING:
            raise
        return job
    except PermanentGmailSyncError as exc:
        _mark_failed(db, job, exc.error_type, str(exc), started)
        return job
    except Exception as exc:
        _mark_failed(db, job, exc.__class__.__name__, str(exc), started)
        return job

    _mark_succeeded(db, job, stats, started)
    return job


def _mark_succeeded(db: Session, job: SyncJob, stats: GmailSyncStats, started: float) -> None:
    job.status = SYNC_STATUS_SUCCEEDED
    job.synced_count = stats.synced_count
    job.created_count = stats.created_count
    job.updated_count = stats.updated_count
    job.finished_at = datetime.now(UTC)
    duration_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "sync.completed",
        extra={
            "sync_job_id": job.id,
            "user_id": job.user_id,
            "gmail_account_id": job.gmail_account_id,
            "message_count": stats.synced_count,
            "created_count": stats.created_count,
            "updated_count": stats.updated_count,
            "duration_ms": duration_ms,
        },
    )
    db.commit()


def _mark_transient_failure(db: Session, job: SyncJob, exc: TransientGmailSyncError, started: float) -> None:
    if job.attempt_count < job.max_attempts:
        job.status = SYNC_STATUS_RETRYING
        event_name = "sync.retry_scheduled"
    else:
        job.status = SYNC_STATUS_FAILED
        job.finished_at = datetime.now(UTC)
        event_name = "sync.failed"
    job.error_type = exc.error_type
    job.error_message = str(exc)
    duration_ms = int((time.perf_counter() - started) * 1000)
    logger.warning(
        event_name,
        extra={
            "sync_job_id": job.id,
            "user_id": job.user_id,
            "gmail_account_id": job.gmail_account_id,
            "attempt_count": job.attempt_count,
            "duration_ms": duration_ms,
            "error_type": job.error_type,
        },
    )
    db.commit()


def _mark_failed(db: Session, job: SyncJob, error_type: str, error_message: str, started: float) -> None:
    job.status = SYNC_STATUS_FAILED
    job.error_type = error_type
    job.error_message = error_message
    job.finished_at = datetime.now(UTC)
    duration_ms = int((time.perf_counter() - started) * 1000)
    logger.warning(
        "sync.failed",
        extra={
            "sync_job_id": job.id,
            "user_id": job.user_id,
            "gmail_account_id": job.gmail_account_id,
            "attempt_count": job.attempt_count,
            "duration_ms": duration_ms,
            "error_type": error_type,
        },
    )
    db.commit()
