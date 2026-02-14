from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import load_config, load_reply_text
from connectors import get_connector_class
from storage.history import ReviewHistory


def setup_logging(log_dir: str) -> None:
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = f"{log_dir}/run_{date_str}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="리뷰 답글 반자동/조회 스크립트")
    parser.add_argument(
        "--mode",
        choices=["reply", "list"],
        default="reply",
        help="reply: 답글 등록 실행, list: 답글 가능한 리뷰 조회만",
    )
    return parser.parse_args()


def print_eligible_reviews(platform_name: str, items) -> None:
    print(f"\n=== [{platform_name}] 답글 가능한 리뷰 {len(items)}건 ===")
    for idx, item in enumerate(items, start=1):
        print(f"{idx}. review_id={item.review_id} | 작성일={item.date_text} | 경과={item.age_days}일")
        print(f"   내용: {item.review_text[:200]}")


def main() -> None:
    args = parse_args()
    cfg = load_config(str(Path(__file__).with_name("config.yaml")))
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(str(cfg.log_dir))

    reply_text = load_reply_text(cfg.reply_text_path)
    history = ReviewHistory(cfg.db_path)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.headless, slow_mo=cfg.slow_mo_ms)

        for platform_name, platform_cfg in cfg.platforms.items():
            if not platform_cfg.enabled:
                continue

            connector_cls = get_connector_class(platform_name)

            logging.info("=== [%s] 시작 (%s 모드) ===", platform_name, args.mode)
            context = browser.new_context(storage_state=platform_cfg.storage_state)
            connector = connector_cls(platform_cfg, cfg, history, reply_text)

            if args.mode == "list":
                eligible = connector.list_eligible(context)
                print_eligible_reviews(platform_name, eligible)
            else:
                connector.run(context)

            context.storage_state(path=platform_cfg.storage_state)
            context.close()
            logging.info("=== [%s] 완료 ===", platform_name)

        browser.close()

    history.close()


if __name__ == "__main__":
    main()
