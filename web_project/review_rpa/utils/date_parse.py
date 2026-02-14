from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


DATE_FORMAT_CANDIDATES = [
    "%Y-%m-%d",
    "%Y.%m.%d",
    "%Y/%m/%d",
    "%Y-%m-%d %H:%M",
    "%Y.%m.%d %H:%M",
    "%Y/%m/%d %H:%M",
]


def parse_review_date(raw_text: str, tz_name: str = "Asia/Seoul") -> datetime:
    cleaned = " ".join(raw_text.strip().split())
    tz = ZoneInfo(tz_name)

    for fmt in DATE_FORMAT_CANDIDATES:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.replace(tzinfo=tz)
        except ValueError:
            continue

    raise ValueError(f"지원하지 않는 날짜 형식: {raw_text}")


def age_in_days(review_dt: datetime, now_dt: datetime) -> int:
    return (now_dt.date() - review_dt.date()).days
