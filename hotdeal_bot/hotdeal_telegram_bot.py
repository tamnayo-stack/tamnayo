import asyncio
import json
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable, List
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup
import telegram


# =========================
# 1) 설정
# =========================
@dataclass
class BotConfig:
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", ""))
    chat_id: str = field(default_factory=lambda: os.getenv("CHAT_ID", ""))
    base_url: str = field(default_factory=lambda: os.getenv("HOTDEAL_URL", "https://algumon.com/"))
    check_interval_sec: int = field(default_factory=lambda: int(os.getenv("CHECK_INTERVAL_SEC", "60")))
    request_timeout_sec: int = field(default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT_SEC", "15")))
    db_path: str = field(default_factory=lambda: os.getenv("SEEN_DB_PATH", "seen_posts.db"))
    keyword_file: str = field(default_factory=lambda: os.getenv("KEYWORD_FILE", "keywords.json"))
    startup_test_message: bool = field(
        default_factory=lambda: os.getenv("STARTUP_TEST_MESSAGE", "true").lower() == "true"
    )
    dry_run: bool = field(default_factory=lambda: os.getenv("DRY_RUN", "false").lower() == "true")

    def validate(self) -> None:
        if not self.telegram_token and not self.dry_run:
            raise ValueError("TELEGRAM_TOKEN이 비어 있습니다. 환경변수 또는 코드에서 설정하세요.")
        if not self.chat_id and not self.dry_run:
            raise ValueError("CHAT_ID가 비어 있습니다. 환경변수 또는 코드에서 설정하세요.")
        if self.check_interval_sec < 10:
            raise ValueError("CHECK_INTERVAL_SEC는 10초 이상으로 설정하세요.")


# =========================
# 2) 저장소
# =========================
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


# =========================
# 3) 키워드 관리자
# =========================
class KeywordManager:
    def __init__(self, keyword_file: str, default_keywords: Iterable[str] | None = None):
        self.keyword_file = keyword_file
        self._lock = threading.Lock()
        self._keywords = set(default_keywords or {"4070", "특가", "오류", "대란"})
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

    def match(self, text: str) -> bool:
        text_lower = text.lower()
        with self._lock:
            return any(k.lower() in text_lower for k in self._keywords)


def start_cli_keyword_console(manager: KeywordManager, stop_event: threading.Event) -> None:
    print("\n" + "=" * 50)
    print("📢 [명령어 가이드]")
    print(" - 추가: add 키워드 (예: add 치킨)")
    print(" - 삭제: del 키워드 (예: del 치킨)")
    print(" - 목록: list")
    print(" - 종료: exit")
    print("=" * 50 + "\n")

    while not stop_event.is_set():
        try:
            command = input().strip()
            if not command:
                continue
            parts = command.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "add":
                if manager.add(arg):
                    print(f"✅ [{arg}] 추가됨")
                else:
                    print("⚠️ 추가 실패(빈 값이거나 이미 존재)")
            elif cmd == "del":
                if manager.remove(arg):
                    print(f"🗑️ [{arg}] 삭제됨")
                else:
                    print(f"❌ [{arg}] 키워드 없음")
            elif cmd == "list":
                print("📋 현재 키워드:", manager.list_keywords())
            elif cmd == "exit":
                print("종료 요청을 받았습니다.")
                stop_event.set()
            else:
                print("알 수 없는 명령어입니다.")
        except EOFError:
            stop_event.set()
            return
        except Exception as exc:
            print(f"명령어 에러: {exc}")


# =========================
# 4) 핫딜 봇
# =========================
class HotdealBot:
    def __init__(self, config: BotConfig):
        self.config = config
        self.repo = SeenPostRepository(config.db_path)
        self.keywords = KeywordManager(config.keyword_file)
        self.stop_event = threading.Event()
        self.bot = telegram.Bot(token=config.telegram_token) if not config.dry_run else None

    async def send_message(self, text: str) -> None:
        if self.config.dry_run:
            logging.info("[DRY_RUN] 메시지 전송 스킵: %s", text.replace("\n", " | "))
            return
        assert self.bot is not None
        await self.bot.send_message(chat_id=self.config.chat_id, text=text, disable_web_page_preview=False)

    async def fetch_page(self, session: aiohttp.ClientSession) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }
        async with session.get(self.config.base_url, headers=headers, timeout=self.config.request_timeout_sec) as resp:
            if resp.status != 200:
                raise RuntimeError(f"접속 실패: HTTP {resp.status}")
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

    async def check_once(self, session: aiohttp.ClientSession) -> int:
        html = await self.fetch_page(session)
        posts = self.parse_posts(html, self.config.base_url)

        sent_count = 0
        for post in posts:
            post_id = post["post_id"]
            title = post["title"]
            link = post["link"]

            if self.repo.has(post_id):
                continue

            if self.keywords.match(title):
                msg = f"🚨 키워드 발견\n🛍️ {title}\n🔗 {link}"
                await self.send_message(msg)
                sent_count += 1
                logging.info("알림 발송: %s", title)

            self.repo.add(post_id, title, link)

        return sent_count

    async def run(self) -> None:
        if self.config.startup_test_message:
            await self.send_message("🔔 [알림] 핫딜 봇이 정상 시작되었습니다.")

        cli_thread = threading.Thread(
            target=start_cli_keyword_console,
            args=(self.keywords, self.stop_event),
            daemon=True,
        )
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
                await asyncio.sleep(self.config.check_interval_sec)


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

    logging.info("핫딜 감시 시작 (interval=%ss, dry_run=%s)", config.check_interval_sec, config.dry_run)
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
