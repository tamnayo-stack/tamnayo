from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.connectors.factory import get_connector
from app.models.entities import PlatformConnection, Review
from app.services.encryption import decrypt_value


def sync_connection_reviews(db: Session, connection: PlatformConnection) -> int:
    connector = get_connector(connection.platform)
    reviews = connector.list_reviews(decrypt_value(connection.encrypted_secret))

    count = 0
    for rv in reviews:
        stmt = insert(Review).values(
            connection_id=connection.id,
            platform_review_id=rv.review_id,
            customer_name=rv.customer_name,
            menu_name=rv.menu_name,
            content=rv.content,
            reviewed_at=rv.reviewed_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["connection_id", "platform_review_id"],
            set_={
                "customer_name": rv.customer_name,
                "menu_name": rv.menu_name,
                "content": rv.content,
                "reviewed_at": rv.reviewed_at,
            },
        )
        db.execute(stmt)
        count += 1
    db.commit()
    return count


def sync_all_connections(db: Session) -> int:
    connections = db.scalars(select(PlatformConnection)).all()
    total = 0
    for connection in connections:
        total += sync_connection_reviews(db, connection)
    return total
