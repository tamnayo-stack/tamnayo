from celery import Celery

from app.core.config import settings

celery_app = Celery("review_worker", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.beat_schedule = {
    "sync-reviews-periodic": {
        "task": "app.workers.tasks.sync_reviews_task",
        "schedule": settings.scheduler_interval_seconds,
    },
    "post-replies-periodic": {
        "task": "app.workers.tasks.post_reply_task",
        "schedule": 30,
    },
}
