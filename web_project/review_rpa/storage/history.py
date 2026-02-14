from __future__ import annotations

import sqlite3
from pathlib import Path


class ReviewHistory:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._init_table()

    def _init_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS replied_reviews (
                platform TEXT NOT NULL,
                review_id TEXT NOT NULL,
                replied_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(platform, review_id)
            )
            """
        )
        self.conn.commit()

    def exists(self, platform: str, review_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM replied_reviews WHERE platform = ? AND review_id = ?",
            (platform, review_id),
        ).fetchone()
        return row is not None

    def add(self, platform: str, review_id: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO replied_reviews(platform, review_id) VALUES(?, ?)",
            (platform, review_id),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
