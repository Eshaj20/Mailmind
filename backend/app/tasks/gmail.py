from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.gmail import TransientGmailSyncError
from app.services.sync_jobs import process_sync_job

# Define a Celery task for synchronizing a Gmail account, which takes a sync job ID as input. The task creates a database session, processes the sync job, and handles transient errors by retrying the task up to three times with a delay of 30 seconds between retries. Finally, it ensures that the database session is closed after processing.

@celery_app.task(bind=True, name="app.tasks.gmail.sync_gmail_account_task", max_retries=3, default_retry_delay=30)

# The sync_gmail_account_task function is a Celery task that processes a Gmail sync job. It creates a database session, calls the process_sync_job function to handle the sync, and manages transient errors by retrying the task if necessary. The database session is closed after processing, regardless of success or failure.
def sync_gmail_account_task(self, sync_job_id: int) -> int:
    db = SessionLocal()
    try:
        process_sync_job(db, sync_job_id=sync_job_id, raise_for_retry=True)
        return sync_job_id
    except TransientGmailSyncError as exc:
        raise self.retry(exc=exc)
    finally:
        db.close()
