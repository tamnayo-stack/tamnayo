from dataclasses import dataclass
from datetime import datetime


@dataclass
class ConnectorReview:
    review_id: str
    customer_name: str
    menu_name: str
    content: str
    reviewed_at: datetime


class PlatformConnector:
    def list_reviews(self, secret: str) -> list[ConnectorReview]:
        raise NotImplementedError

    def post_reply(self, secret: str, review_id: str, content: str) -> tuple[bool, str]:
        raise NotImplementedError
