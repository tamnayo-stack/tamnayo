from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import yaml


@dataclass
class PlatformConfig:
    name: str
    enabled: bool
    base_url: str
    review_page_url: str
    storage_state: str


@dataclass
class AppConfig:
    min_age_days: int
    max_age_days: int
    reply_text_path: Path
    log_dir: Path
    db_path: Path
    headless: bool
    slow_mo_ms: int
    timezone: str
    platforms: Dict[str, PlatformConfig]


def load_config(path: str = "config.yaml") -> AppConfig:
    config_path = Path(path).resolve()
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    base_dir = config_path.parent

    platforms: Dict[str, PlatformConfig] = {}
    for name, item in raw["platforms"].items():
        platforms[name] = PlatformConfig(
            name=name,
            enabled=item.get("enabled", True),
            base_url=item["base_url"],
            review_page_url=item["review_page_url"],
            storage_state=item["storage_state"],
        )

    return AppConfig(
        min_age_days=raw["MIN_AGE_DAYS"],
        max_age_days=raw["MAX_AGE_DAYS"],
        reply_text_path=(base_dir / raw["REPLY_TEXT_PATH"]).resolve(),
        log_dir=(base_dir / raw["LOG_DIR"]).resolve(),
        db_path=(base_dir / raw["DB_PATH"]).resolve(),
        headless=raw.get("HEADLESS", False),
        slow_mo_ms=raw.get("SLOW_MO_MS", 0),
        timezone=raw.get("TIMEZONE", "Asia/Seoul"),
        platforms=platforms,
    )


def load_reply_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"답글 텍스트 파일이 비어 있습니다: {path}")
    return text
