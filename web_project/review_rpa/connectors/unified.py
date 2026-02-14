from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from playwright.sync_api import BrowserContext, Locator, Page

from config import AppConfig, PlatformConfig
from storage.history import ReviewHistory
from utils.date_parse import age_in_days, parse_review_date
from utils.ui import click_if_enabled, wait_for_manual_login


@dataclass
class ReviewItem:
    review_id: str
    date_text: str
    review_text: str
    has_owner_reply: bool
    card: Locator


@dataclass
class EligibleReview:
    platform: str
    review_id: str
    age_days: int
    date_text: str
    review_text: str


class UnifiedReviewConnector:
    """모든 플랫폼을 단일 로직으로 처리하는 통합 커넥터."""

    def __init__(
        self,
        platform: PlatformConfig,
        app_config: AppConfig,
        history: ReviewHistory,
        reply_text: str,
    ):
        self.platform = platform
        self.app_config = app_config
        self.history = history
        self.reply_text = reply_text

    def run(self, context: BrowserContext) -> None:
        if not self.platform.enabled:
            logging.info("[%s] disabled", self.platform.name)
            return

        page = context.new_page()
        self.open_review_page(page)
        self.ensure_authenticated(page)
        reviews = self.collect_reviews(page)
        now_dt = datetime.now()

        for review in reviews:
            try:
                self.process_review(page, review, now_dt)
            except Exception as e:  # noqa: BLE001
                logging.exception("[%s] 리뷰 처리 실패: %s", self.platform.name, e)

    def list_eligible(self, context: BrowserContext) -> List[EligibleReview]:
        page = context.new_page()
        self.open_review_page(page)
        self.ensure_authenticated(page)
        reviews = self.collect_reviews(page)
        now_dt = datetime.now()

        eligible: List[EligibleReview] = []
        for review in reviews:
            try:
                item = self.get_eligible_review(review, now_dt)
                if item is not None:
                    eligible.append(item)
            except Exception as e:  # noqa: BLE001
                logging.exception("[%s] 조회 중 리뷰 판정 실패: %s", self.platform.name, e)

        return eligible

    def open_review_page(self, page: Page) -> None:
        page.goto(self.platform.review_page_url, wait_until="domcontentloaded")

    def ensure_authenticated(self, page: Page) -> None:
        # 로그인/2FA/캡차 우회 금지: 로그인 화면으로 판단되면 수동 처리 대기
        if any(key in page.url.lower() for key in ("login", "signin", "auth", "captcha")):
            logging.info("[%s] 로그인/인증 화면 감지. 수동 처리를 기다립니다.", self.platform.name)
            wait_for_manual_login(page)

    def collect_reviews(self, page: Page) -> List[ReviewItem]:
        cards = page.get_by_role("article")
        items: List[ReviewItem] = []

        for i in range(cards.count()):
            card = cards.nth(i)
            # TODO(unified): 플랫폼별 실제 DOM에 맞게 리뷰ID/날짜/답글여부/리뷰본문 추출을 분리/구체화
            review_id = card.get_attribute("data-review-id") or f"{self.platform.name}-{i}"
            date_text = card.get_by_text("20", exact=False).first.inner_text()
            has_reply = card.get_by_text("사장님 답글", exact=False).count() > 0
            review_text = card.inner_text().strip()[:500]
            items.append(
                ReviewItem(
                    review_id=review_id,
                    date_text=date_text,
                    review_text=review_text,
                    has_owner_reply=has_reply,
                    card=card,
                )
            )

        return items

    def get_eligible_review(self, review: ReviewItem, now_dt: datetime) -> Optional[EligibleReview]:
        review_dt = parse_review_date(review.date_text, self.app_config.timezone)
        days = age_in_days(review_dt, now_dt)

        if days < self.app_config.min_age_days or days > self.app_config.max_age_days:
            return None
        if review.has_owner_reply:
            return None
        if self.history.exists(self.platform.name, review.review_id):
            return None

        reply_btn = review.card.get_by_role("button", name="댓글 작성")
        try:
            if reply_btn.count() == 0 or reply_btn.is_disabled():
                return None
        except Exception:  # noqa: BLE001
            return None

        return EligibleReview(
            platform=self.platform.name,
            review_id=review.review_id,
            age_days=days,
            date_text=review.date_text,
            review_text=review.review_text,
        )

    def process_review(self, page: Page, review: ReviewItem, now_dt: datetime) -> None:
        eligible = self.get_eligible_review(review, now_dt)
        if eligible is None:
            logging.info("[%s] %s: 조건 불일치로 스킵", self.platform.name, review.review_id)
            return

        reply_btn = review.card.get_by_role("button", name="댓글 작성")
        if not click_if_enabled(reply_btn, f"{self.platform.name}:{review.review_id}:댓글 작성"):
            return

        review.card.get_by_role("textbox").fill(self.reply_text)

        submit_btn = review.card.get_by_role("button", name="등록")
        if not click_if_enabled(submit_btn, f"{self.platform.name}:{review.review_id}:등록"):
            return

        self.history.add(self.platform.name, review.review_id)
        logging.info("[%s] %s: 답글 등록 완료", self.platform.name, review.review_id)
