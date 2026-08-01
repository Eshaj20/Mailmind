from app.tasks.gmail import sync_gmail_account_task


class SyncJobQueue:
    def enqueue(self, sync_job_id: int) -> str | None:
        result = sync_gmail_account_task.delay(sync_job_id)
        return getattr(result, "id", None)
