import random

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.gmail import TransientGmailSyncError
from app.services.sync_jobs import (
    SYNC_STATUS_FAILED,
    SYNC_STATUS_SUCCEEDED,
    create_continuation_sync_job,
    process_sync_job,
)

@celery_app.task(
    bind=True,
    name="app.tasks.gmail.sync_gmail_account_task",
    max_retries=settings.sync_job_max_attempts,
)
def sync_gmail_account_task(self, sync_job_id: int) -> int:
    db = SessionLocal()
    try:
        job = process_sync_job(db, sync_job_id=sync_job_id, raise_for_retry=True)
        if job.status == SYNC_STATUS_SUCCEEDED and job.has_more:
            next_job = create_continuation_sync_job(db, job)
            if next_job is not None and not next_job.celery_task_id:
                try:
                    result = self.apply_async(args=[next_job.id])
                    next_job.celery_task_id = getattr(result, "id", None)
                except Exception as exc:
                    next_job.status = SYNC_STATUS_FAILED
                    next_job.error_type = "queue_unavailable"
                    next_job.error_message = str(exc)
                db.commit()
        return sync_job_id
    except TransientGmailSyncError as exc:
        retries = int(getattr(self.request, "retries", 0))
        exponential_delay = settings.sync_retry_base_seconds * (2**retries)
        countdown = min(settings.sync_retry_max_seconds, exponential_delay) + random.uniform(0, 1)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()
