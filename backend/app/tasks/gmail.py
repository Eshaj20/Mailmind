from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.gmail import TransientGmailSyncError
from app.services.sync_jobs import process_sync_job


@celery_app.task(bind=True, name="app.tasks.gmail.sync_gmail_account_task", max_retries=3, default_retry_delay=30)
def sync_gmail_account_task(self, sync_job_id: int) -> int:
    db = SessionLocal()
    try:
        process_sync_job(db, sync_job_id=sync_job_id, raise_for_retry=True)
        return sync_job_id
    except TransientGmailSyncError as exc:
        raise self.retry(exc=exc)
    finally:
        db.close()
