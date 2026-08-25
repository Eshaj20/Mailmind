from app.core.config import settings

try:
    from celery import Celery
except ImportError:  # Keeps local tests usable before dependencies are installed.
    Celery = None  # type: ignore[assignment]


class _ImmediateResult:
    id = "local-immediate"


class _ImmediateTaskRequest:
    retries = 0

# The _ImmediateTask and _ImmediateCelery classes provide a mock implementation of Celery tasks for local testing purposes. They allow for immediate execution of tasks without requiring a running Celery worker or broker. The _ImmediateTask class simulates a Celery task, while the _ImmediateCelery class provides a decorator to create immediate tasks. This setup is useful for testing and development environments where Celery is not available.
class _ImmediateTask:
    def __init__(self, func, bind: bool = False):
        self.func = func
        self.bind = bind
        self.request = _ImmediateTaskRequest()

    def delay(self, *args, **kwargs):
        if self.bind:
            self.func(self, *args, **kwargs)
        else:
            self.func(*args, **kwargs)
        return _ImmediateResult()

    def retry(self, exc=None):
        if exc:
            raise exc
        raise RuntimeError("Immediate task retry requested")

    def __call__(self, *args, **kwargs):
        if self.bind:
            return self.func(self, *args, **kwargs)
        return self.func(*args, **kwargs)


class _ImmediateCelery:
    def task(self, *args, **kwargs):
        def decorator(func):
            return _ImmediateTask(func, bind=bool(kwargs.get("bind")))

        return decorator


if Celery is None:
    celery_app = _ImmediateCelery()
else:
    celery_app = Celery(
        "mailmind",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.tasks.gmail"],
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        task_track_started=True,
    )
