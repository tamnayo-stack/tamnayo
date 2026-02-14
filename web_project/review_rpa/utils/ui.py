from __future__ import annotations

import logging
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError


def click_if_enabled(target: Locator, label: str, timeout_ms: int = 3000) -> bool:
    try:
        target.wait_for(state="visible", timeout=timeout_ms)
        if target.is_disabled():
            logging.info("[SKIP] %s 비활성", label)
            return False
        target.click()
        return True
    except PlaywrightTimeoutError:
        logging.info("[SKIP] %s 요소 없음/대기시간 초과", label)
        return False


def wait_for_manual_login(page: Page, timeout_sec: int = 300) -> bool:
    logging.info("로그인/2FA/캡차 발생 가능. 브라우저에서 직접 완료하세요.")
    try:
        page.get_by_role("button", name="로그아웃").wait_for(timeout=timeout_sec * 1000)
        logging.info("로그인 완료 감지(로그아웃 버튼 확인)")
        return True
    except PlaywrightTimeoutError:
        logging.warning("로그인 완료 신호를 감지하지 못했습니다. 다음 단계 진행 시도")
        return False
