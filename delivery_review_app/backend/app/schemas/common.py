from datetime import datetime

from pydantic import BaseModel


class StoreCreate(BaseModel):
    name: str


class StoreRead(StoreCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ConnectionCreate(BaseModel):
    store_id: int
    platform: str
    login_id: str
    password: str


class ConnectionRead(BaseModel):
    id: int
    store_id: int
    platform: str
    login_id: str
    created_at: datetime
    synced_reviews: int = 0


class TemplateCreate(BaseModel):
    name: str
    body: str


class TemplateRead(TemplateCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BulkReplyCreate(BaseModel):
    review_ids: list[int]
    template_id: int


class ReviewQuery(BaseModel):
    start_date: datetime | None = None
    end_date: datetime | None = None
    tab: str = "ALL"
