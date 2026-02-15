import asyncio
import json
import logging
import os
import re
import signal
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
import telegram


@dataclass
class BotConfig:
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", "8408404594:AAGI3WD9MNOpzVWtlowZZjmuYfmFDDO8xW0"))
    chat_id: str = field(default_factory=lambda: os.getenv("CHAT_ID", "8408697849"))
    base_url: str = field(default_factory=lambda: os.getenv("HOTDEAL_URL", "https://algumon.com/"))
    check_interval_sec: int = field(default_factory=lambda: int(os.getenv("CHECK_INTERVAL_SEC", "60")))
    request_timeout_sec: int = field(default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT_SEC", "15")))
    db_path: str = field(default_factory=lambda: os.getenv("SEEN_DB_PATH", "seen_posts.db"))
    keyword_file: str = field(default_factory=lambda: os.getenv("KEYWORD_FILE", "keywords.json"))
    startup_test_message: bool = field(
        default_factory=lambda: os.getenv("STARTUP_TEST_MESSAGE", "true").lower() == "true"
    )
    dry_run: bool = field(default_factory=lambda: os.getenv("DRY_RUN", "false").lower() == "true")
    include_origin_link: bool = field(
        default_factory=lambda: os.getenv("INCLUDE_ORIGIN_LINK", "true").lower() == "true"
    )
    keyword_alert_repeat: int = field(default_factory=lambda: int(os.getenv("KEYWORD_ALERT_REPEAT", "3")))

    def validate(self) -> None:
        if not self.telegram_token and not self.dry_run:
            raise ValueError("TELEGRAM_TOKEN이 비어 있습니다.")
        if not self.chat_id and not self.dry_run:
            raise ValueError("CHAT_ID가 비어 있습니다.")
        if self.check_interval_sec < 5:
            raise ValueError("CHECK_INTERVAL_SEC는 5초 이상으로 설정하세요.")
        if self.keyword_alert_repeat < 1:
            raise ValueError("KEYWORD_ALERT_REPEAT는 1 이상이어야 합니다.")


class SeenPostRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_posts (
                    post_id TEXT PRIMARY KEY,
                    title TEXT,
                    link TEXT,
                    seen_at INTEGER
                )
                """
            )
            conn.commit()

    def has(self, post_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM seen_posts WHERE post_id = ?", (post_id,)).fetchone()
            return row is not None

    def add(self, post_id: str, title: str, link: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO seen_posts (post_id, title, link, seen_at) VALUES (?, ?, ?, ?)",
                (post_id, title, link, int(time.time())),
            )
            conn.commit()


class KeywordManager:
    def __init__(self, keyword_file: str, default_keywords: Iterable[str] | None = None):
        self.keyword_file = keyword_file
        self._lock = threading.Lock()
        self._keywords = set(default_keywords or set())
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.keyword_file):
            self._save()
            return
        try:
            with open(self.keyword_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            loaded = payload.get("keywords", [])
            if isinstance(loaded, list):
                self._keywords = {str(item).strip() for item in loaded if str(item).strip()}
        except Exception as exc:
            logging.warning("키워드 파일 로드 실패: %s", exc)

    def _save(self) -> None:
        with open(self.keyword_file, "w", encoding="utf-8") as f:
            json.dump({"keywords": sorted(self._keywords)}, f, ensure_ascii=False, indent=2)

    def list_keywords(self) -> List[str]:
        with self._lock:
            return sorted(self._keywords)

    def add(self, keyword: str) -> bool:
        keyword = keyword.strip()
        if not keyword:
            return False
        with self._lock:
            before = len(self._keywords)
            self._keywords.add(keyword)
            changed = len(self._keywords) > before
            if changed:
                self._save()
            return changed

    def remove(self, keyword: str) -> bool:
        keyword = keyword.strip()
        with self._lock:
            if keyword not in self._keywords:
                return False
            self._keywords.remove(keyword)
            self._save()
            return True

    def matched_keywords(self, text: str) -> List[str]:
        text_lower = text.lower()
        with self._lock:
            return [k for k in sorted(self._keywords) if k.lower() in text_lower]


class HotdealBot:
    def __init__(self, config: BotConfig):
        self.config = config
        self.repo = SeenPostRepository(config.db_path)
        self.keywords = KeywordManager(config.keyword_file)
        self.stop_event = threading.Event()
        self.bot = telegram.Bot(token=config.telegram_token) if not config.dry_run else None
        self.base_host = urlparse(config.base_url).netloc.lower()
        self._interval_lock = threading.Lock()

    def get_interval_sec(self) -> int:
        with self._interval_lock:
            return self.config.check_interval_sec

    def set_interval_sec(self, value: str) -> bool:
        try:
            sec = int(value.strip())
        except ValueError:
            return False
        if sec < 5:
            return False
        with self._interval_lock:
            self.config.check_interval_sec = sec
        return True

    def print_console_help(self) -> None:
        print("\n" + "=" * 54)
        print("📢 [명령어 가이드]")
        print(" - add 키워드      (예: add 치킨)")
        print(" - del 키워드      (예: del 치킨)")
        print(" - sec 숫자        (예: sec 20) -> 체크 주기(초)")
        print(" - status")
        print(" - exit")
        print("=" * 54 + "\n")

    def run_console(self) -> None:
        self.print_console_help()
        while not self.stop_event.is_set():
            try:
                command = input().strip()
                if not command:
                    continue
                parts = command.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""

                if cmd == "add":
                    if self.keywords.add(arg):
                        print(f"✅ [{arg}] 추가됨")
                    else:
                        print("⚠️ 추가 실패(빈 값이거나 이미 존재)")
                elif cmd == "del":
                    if self.keywords.remove(arg):
                        print(f"🗑️ [{arg}] 삭제됨")
                    else:
                        print(f"❌ [{arg}] 키워드 없음")
                elif cmd == "sec":
                    if self.set_interval_sec(arg):
                        print(f"✅ 체크 주기 변경: {self.get_interval_sec()}초")
                    else:
                        print("❌ sec 값 오류. 5 이상의 정수를 입력하세요.")
                elif cmd == "status":
                    print(
                        f"ℹ️ all모드(고정), interval={self.get_interval_sec()}초, "
                        f"keyword_alert_repeat={self.config.keyword_alert_repeat}, "
                        f"keywords={self.keywords.list_keywords()}"
                    )
                elif cmd == "exit":
                    print("종료 요청을 받았습니다.")
                    self.stop_event.set()
                else:
                    print("알 수 없는 명령어입니다.")
            except EOFError:
                self.stop_event.set()
                return
            except Exception as exc:
                print(f"명령어 에러: {exc}")

    async def send_message(self, text: str) -> None:
        if self.config.dry_run:
            logging.info("[DRY_RUN] 메시지 전송 스킵: %s", text.replace("\n", " | "))
            return
        assert self.bot is not None
        await self.bot.send_message(chat_id=self.config.chat_id, text=text, disable_web_page_preview=False)

    async def fetch_html(self, session: aiohttp.ClientSession, url: str) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }
        async with session.get(url, headers=headers, timeout=self.config.request_timeout_sec) as resp:
            if resp.status != 200:
                raise RuntimeError(f"접속 실패: HTTP {resp.status} ({url})")
            return await resp.text()

    @staticmethod
    def parse_posts(html: str, base_url: str) -> List[dict]:
        soup = BeautifulSoup(html, "html.parser")
        posts = []
        for li in soup.select(".post-list li"):
            title_tag = li.select_one(".product-body .item-name")
            link_tag = li.select_one(".product-body a[href]")
            if not title_tag or not link_tag:
                continue
            title = title_tag.get_text(strip=True)
            href = link_tag.get("href", "")
            if not href:
                continue
            link = urljoin(base_url, href)
            post_id = href.rstrip("/").split("/")[-1] or link.rstrip("/").split("/")[-1]
            posts.append({"post_id": post_id, "title": title, "link": link})
        return posts

    def _is_external_link(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if not parsed.netloc:
            return False
        if parsed.netloc.lower().endswith(self.base_host):
            return False
        return True

    def parse_origin_link(self, html: str, page_url: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        selectors = [
            "a.product-link[href]",
            "a.btn-info[href]",
            "a.btn-primary[href]",
            "article a[href]",
            ".content a[href]",
            ".xe_content a[href]",
            ".rd_body a[href]",
            ".board_read a[href]",
            "a[href]",
        ]
        for selector in selectors:
            for tag in soup.select(selector):
                href = (tag.get("href") or "").strip()
                if not href:
                    continue
                abs_url = urljoin(page_url, href)
                if self._is_external_link(abs_url):
                    return abs_url
        return None

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def parse_deal_fields(self, html: str, page_url: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        result = {
            "origin_link": self.parse_origin_link(html, page_url),
            "price": None,
            "shipping": None,
            "seller": None,
            "content": None,
        }

        aliases = {
            "price": ("가격", "판매가", "금액"),
            "shipping": ("배송", "배송비", "배송/직배", "직배"),
            "seller": ("판매처", "쇼핑몰", "몰", "스토어"),
            "origin_link": ("링크", "구매링크", "원문링크", "url"),
        }

        for row in soup.select("tr"):
            key_cell = row.select_one("th, dt, strong, .tit, .label")
            val_cell = row.select_one("td, dd, .value, .txt")
            if not key_cell or not val_cell:
                continue

            key_text = self._clean_text(key_cell.get_text(" ", strip=True)).lower()
            value_text = self._clean_text(val_cell.get_text(" ", strip=True))
            if not value_text:
                continue

            for field_name, label_candidates in aliases.items():
                if result.get(field_name):
                    continue
                if any(label.lower() in key_text for label in label_candidates):
                    result[field_name] = value_text
                    if field_name == "origin_link":
                        a_tag = val_cell.select_one("a[href]")
                        if a_tag:
                            abs_url = urljoin(page_url, (a_tag.get("href") or "").strip())
                            if self._is_external_link(abs_url):
                                result["origin_link"] = abs_url

        for selector in [".xe_content", ".rd_body", ".content", "article", ".board_read"]:
            section = soup.select_one(selector)
            if section:
                snippet = self._clean_text(section.get_text(" ", strip=True))
                if snippet:
                    result["content"] = snippet[:220]
                    break

        return result

    async def resolve_deal_fields(self, session: aiohttp.ClientSession, post_link: str) -> dict:
        if not self.config.include_origin_link:
            return {"origin_link": None, "price": None, "shipping": None, "seller": None, "content": None}
        try:
            detail_html = await self.fetch_html(session, post_link)
            return self.parse_deal_fields(detail_html, post_link)
        except Exception as exc:
            logging.debug("상세 정보 추출 실패 (%s): %s", post_link, exc)
            return {"origin_link": None, "price": None, "shipping": None, "seller": None, "content": None}

    def build_alert_message(self, title: str, algo_link: str, deal: dict) -> str:
        # 고정 포맷: 핫딜발견 / 제목 / 내용 / 알구몬링크 / 구매링크
        lines = ["🚨 핫딜발견", f"제목: {title}"]

        content_parts = []
        if deal.get("seller"):
            content_parts.append(f"판매처 {deal['seller']}")
        if deal.get("price"):
            content_parts.append(f"가격 {deal['price']}")
        if deal.get("shipping"):
            content_parts.append(f"배송 {deal['shipping']}")
        if deal.get("content"):
            content_parts.append(str(deal["content"]))

        lines.append(f"내용: {' | '.join(content_parts) if content_parts else '정보 없음'}")
        lines.append(f"알구몬링크: {algo_link}")
        lines.append(f"구매링크: {deal.get('origin_link') or '없음'}")
        return "\n".join(lines)

    def detect_keyword_hits(self, title: str, deal: dict) -> List[str]:
        haystack = " ".join(
            [
                title,
                str(deal.get("seller") or ""),
                str(deal.get("price") or ""),
                str(deal.get("shipping") or ""),
                str(deal.get("content") or ""),
                str(deal.get("origin_link") or ""),
            ]
        )
        return self.keywords.matched_keywords(haystack)

    async def maybe_send_keyword_alert_burst(self, title: str, base_message: str, matched_keywords: List[str]) -> None:
        if not matched_keywords:
            return
        repeat = max(1, self.config.keyword_alert_repeat)
        if repeat <= 1:
            return
        for idx in range(2, repeat + 1):
            extra_message = (
                f"🚨 [키워드 감지 {idx}/{repeat}] {', '.join(matched_keywords)}\n"
                f"제목: {title}\n"
                f"{base_message}"
            )
            await self.send_message(extra_message)

    async def check_once(self, session: aiohttp.ClientSession) -> int:
        html = await self.fetch_html(session, self.config.base_url)
        posts = self.parse_posts(html, self.config.base_url)

        sent_count = 0
        for post in posts:
            post_id = post["post_id"]
            title = post["title"]
            algo_link = post["link"]

            if self.repo.has(post_id):
                continue

            deal = await self.resolve_deal_fields(session, algo_link)
            message = self.build_alert_message(title, algo_link, deal)
            await self.send_message(message)
            sent_count += 1

            matched_keywords = self.detect_keyword_hits(title, deal)
            await self.maybe_send_keyword_alert_burst(title, message, matched_keywords)

            self.repo.add(post_id, title, algo_link)

        return sent_count

    async def run(self) -> None:
        if self.config.startup_test_message:
            await self.send_message("🔔 [알림] 핫딜 봇이 정상 시작되었습니다.")

        cli_thread = threading.Thread(target=self.run_console, daemon=True)
        cli_thread.start()

        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout_sec)
        connector = aiohttp.TCPConnector(limit=20, ssl=False)

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            while not self.stop_event.is_set():
                try:
                    sent = await self.check_once(session)
                    logging.info("체크 완료: 새 알림 %d건", sent)
                except Exception as exc:
                    logging.exception("체크 중 오류: %s", exc)
                await asyncio.sleep(self.get_interval_sec())


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def install_signal_handlers(loop: asyncio.AbstractEventLoop, stop_event: threading.Event) -> None:
    def _graceful_stop(*_: object) -> None:
        logging.info("종료 시그널 수신. 안전하게 종료합니다.")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _graceful_stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _graceful_stop())


async def async_main() -> None:
    setup_logging()
    config = BotConfig()
    config.validate()

    bot = HotdealBot(config)
    loop = asyncio.get_running_loop()
    install_signal_handlers(loop, bot.stop_event)

    logging.info(
        "핫딜 감시 시작 (interval=%ss, dry_run=%s, all_mode=true, keyword_alert_repeat=%s)",
        config.check_interval_sec,
        config.dry_run,
        config.keyword_alert_repeat,
    )
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
