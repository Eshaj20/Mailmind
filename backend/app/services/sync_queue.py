from app.tasks.gmail import sync_gmail_account_task


class SyncQueueUnavailableError(RuntimeError):
    """Raised when the production queue/broker cannot accept a sync job."""


class SyncJobQueue:
    """Thin adapter around Celery so routes do not depend on broker details."""

    def enqueue(self, sync_job_id: int) -> str | None:
        try:
            result = sync_gmail_account_task.delay(sync_job_id)
            return getattr(result, "id", None)
        except Exception as exc:
            raise SyncQueueUnavailableError("Gmail sync queue is unavailable") from exc
