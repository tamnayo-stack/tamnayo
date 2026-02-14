from sqlalchemy import select

from app.connectors.factory import get_connector
from app.db.session import SessionLocal
from app.models.entities import PlatformConnection, Reply, ReplyJob, ReplyStatus, Review
from app.services.encryption import decrypt_value
from app.services.review_sync import sync_all_connections
from app.workers.celery_app import celery_app


@celery_app.task
def sync_reviews_task():
    with SessionLocal() as db:
        return sync_all_connections(db)


@celery_app.task(bind=True, max_retries=3)
def post_reply_task(self):
    with SessionLocal() as db:
        jobs = db.scalars(select(ReplyJob).where(ReplyJob.status == ReplyStatus.PENDING)).all()
        for job in jobs:
            reply = db.get(Reply, job.reply_id)
            review = db.get(Review, reply.review_id) if reply else None
            connection = db.get(PlatformConnection, review.connection_id) if review else None
            if not (reply and review and connection):
                continue
            connector = get_connector(connection.platform)
            ok, reason = connector.post_reply(
                decrypt_value(connection.encrypted_secret),
                review.platform_review_id,
                reply.content,
            )
            if ok:
                reply.status = ReplyStatus.POSTED
                job.status = ReplyStatus.POSTED
                job.fail_reason = ""
            else:
                reply.status = ReplyStatus.FAILED
                reply.fail_reason = reason
                job.status = ReplyStatus.FAILED
                job.fail_reason = reason
                job.retry_count += 1
        db.commit()
