from app.tasks.gmail import sync_gmail_account_task

# Define a queue class for managing Gmail sync jobs, which provides a method to enqueue a sync job by calling the Celery task and returning the task ID. This class abstracts the queuing mechanism and allows for easy integration with the rest of the application.
class SyncJobQueue:
    def enqueue(self, sync_job_id: int) -> str | None:
        result = sync_gmail_account_task.delay(sync_job_id)
        return getattr(result, "id", None)
