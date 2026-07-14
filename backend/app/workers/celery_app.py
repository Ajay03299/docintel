from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "docintel",
    broker=settings.redis_url,
    backend=settings.redis_url,   # store task results/states in Redis
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,          # so we can see STARTED, not just PENDING→SUCCESS
    task_acks_late=True,              # ack AFTER completion — if worker dies, task requeues
    worker_prefetch_multiplier=1,     # one slow AI task at a time per worker; fair dispatch
    task_time_limit=300,              # hard kill a task after 5 min (zombie guard)
    task_soft_time_limit=270,         # soft warning 30s earlier to clean up gracefully
)

celery_app.conf.imports = ("app.workers.pipeline",)