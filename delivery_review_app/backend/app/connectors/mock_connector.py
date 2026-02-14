import random
from datetime import datetime, timedelta

from app.connectors.base import ConnectorReview, PlatformConnector


class MockConnector(PlatformConnector):
    def list_reviews(self, secret: str) -> list[ConnectorReview]:
        now = datetime.utcnow()
        return [
            ConnectorReview(
                review_id=f"mock-{i}",
                customer_name=f"고객{i}",
                menu_name=random.choice(["치킨", "피자", "떡볶이", ""]),
                content=random.choice(["맛있어요", "보통이에요", "다음엔 더 빨리 주세요"]),
                reviewed_at=now - timedelta(hours=i),
            )
            for i in range(1, 6)
        ]

    def post_reply(self, secret: str, review_id: str, content: str) -> tuple[bool, str]:
        ok = random.random() > 0.25
        return (True, "") if ok else (False, "랜덤 시뮬레이션 실패")
