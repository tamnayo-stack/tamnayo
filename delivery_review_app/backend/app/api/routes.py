from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import PlatformConnection, Reply, ReplyJob, ReplyStatus, Review, Store, Template
from app.schemas.common import BulkReplyCreate, ConnectionCreate, ConnectionRead, StoreCreate, StoreRead, TemplateCreate, TemplateRead
from app.services.encryption import encrypt_value
from app.services.review_sync import sync_all_connections
from app.services.template_engine import render_template

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/stores", response_model=list[StoreRead])
def list_stores(db: Session = Depends(get_db)):
    return db.scalars(select(Store).order_by(Store.id.desc())).all()


@router.post("/stores", response_model=StoreRead)
def create_store(payload: StoreCreate, db: Session = Depends(get_db)):
    row = Store(name=payload.name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/connections", response_model=list[ConnectionRead])
def list_connections(db: Session = Depends(get_db)):
    rows = db.scalars(select(PlatformConnection).order_by(PlatformConnection.id.desc())).all()
    return [
        {
            "id": row.id,
            "store_id": row.store_id,
            "platform": row.platform,
            "login_id": row.account_name,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/connections", response_model=ConnectionRead)
def create_connection(payload: ConnectionCreate, db: Session = Depends(get_db)):
    row = PlatformConnection(
        store_id=payload.store_id,
        platform=payload.platform,
        account_name=payload.login_id,
        encrypted_secret=encrypt_value(payload.password),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "store_id": row.store_id,
        "platform": row.platform,
        "login_id": row.account_name,
        "created_at": row.created_at,
    }


@router.get("/templates", response_model=list[TemplateRead])
def list_templates(db: Session = Depends(get_db)):
    return db.scalars(select(Template).order_by(Template.id.desc())).all()


@router.post("/templates", response_model=TemplateRead)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db)):
    row = Template(name=payload.name, body=payload.body)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/reviews/sync")
def trigger_sync(db: Session = Depends(get_db)):
    synced = sync_all_connections(db)
    return {"synced": synced}


@router.get("/reviews")
def list_reviews(start_date: datetime | None = None, end_date: datetime | None = None, tab: str = "ALL", db: Session = Depends(get_db)):
    query = select(Review, Reply.status).outerjoin(Reply, Reply.review_id == Review.id)
    if start_date:
        query = query.where(Review.reviewed_at >= start_date)
    if end_date:
        query = query.where(Review.reviewed_at <= end_date)

    rows = db.execute(query.order_by(Review.reviewed_at.desc())).all()
    items = []
    for review, status in rows:
        display = "미등록"
        if status == ReplyStatus.PENDING:
            display = "등록대기"
        elif status == ReplyStatus.POSTED:
            display = "완료"
        elif status == ReplyStatus.FAILED:
            display = "미등록"

        if tab != "ALL" and display != tab:
            continue

        items.append(
            {
                "id": review.id,
                "connection_id": review.connection_id,
                "platform_review_id": review.platform_review_id,
                "customer_name": review.customer_name,
                "menu_name": review.menu_name,
                "content": review.content,
                "reviewed_at": review.reviewed_at,
                "tab": display,
            }
        )

    counts = {
        "ALL": len(rows),
        "등록대기": db.scalar(select(func.count(Reply.id)).where(Reply.status == ReplyStatus.PENDING)) or 0,
        "미등록": len([1 for _, s in rows if s is None or s == ReplyStatus.FAILED]),
        "완료": db.scalar(select(func.count(Reply.id)).where(Reply.status == ReplyStatus.POSTED)) or 0,
    }
    return {"items": items, "counts": counts}


@router.post("/replies/bulk")
def create_bulk_replies(payload: BulkReplyCreate, db: Session = Depends(get_db)):
    template = db.get(Template, payload.template_id)
    if not template:
        raise HTTPException(404, "template not found")

    created = 0
    for review_id in payload.review_ids:
        review = db.get(Review, review_id)
        if not review:
            continue
        connection = db.get(PlatformConnection, review.connection_id)
        store = db.get(Store, connection.store_id) if connection else None
        content = render_template(
            template.body,
            {
                "매장명": store.name if store else "",
                "플랫폼": connection.platform if connection else "",
                "고객명": review.customer_name,
                "메뉴": review.menu_name,
            },
        )
        reply = Reply(review_id=review.id, template_id=template.id, content=content, status=ReplyStatus.PENDING)
        db.add(reply)
        db.flush()
        job = ReplyJob(reply_id=reply.id, status=ReplyStatus.PENDING)
        db.add(job)
        created += 1

    db.commit()
    return {"created": created}


@router.get("/reply-jobs")
def list_reply_jobs(db: Session = Depends(get_db)):
    rows = db.scalars(select(ReplyJob).order_by(ReplyJob.id.desc())).all()
    return [
        {
            "id": row.id,
            "reply_id": row.reply_id,
            "status": row.status,
            "retry_count": row.retry_count,
            "fail_reason": row.fail_reason,
        }
        for row in rows
    ]
