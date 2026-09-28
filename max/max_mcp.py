# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "maxapi-python==2.4.1",
#     "mcp>=1.20,<2",
#     "qrcode[pil]>=7.4",
# ]
# ///
"""MAX для Claude Code: личный аккаунт MAX как MCP-сервер.

Сделан по схеме моста Альберта (сервер Гермеса), но всё живёт на компьютере ученика:
- `uv run --script max_mcp.py login`  вход по QR с телефона, сессия в ~/.neovida-messengers/max
- `uv run --script max_mcp.py serve`  MCP по stdio, его запускает Claude Code
- `uv run --script max_mcp.py status` проверка, есть ли сохранённый вход

Пока Claude Code открыт, сервер держит соединение с MAX, пишет новые сообщения
в локальную SQLite и подтягивает историю свежих чатов. Сервер НИКОГДА не
начинает вход сам: если сессия слетела, он честно говорит «запусти login».
Повторные попытки входа MAX не любит (блокирует SMS и может забанить).
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime as dt
import json
import logging
import os
import sqlite3
import sys
import time
import webbrowser
from pathlib import Path

STATE = Path(os.environ.get("NEOVIDA_MAX_DIR", Path.home() / ".neovida-messengers" / "max"))
SESSION = "web-session.db"
BACKFILL_CHATS = 60
BACKFILL_MSGS = 40
LOG = logging.getLogger("neovida_max")


# ---------- хранилище ----------

class Store:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY, type TEXT, title TEXT,
                participants INTEGER, last_time INTEGER);
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER, chat_id INTEGER, sender INTEGER, sender_name TEXT,
                text TEXT, time INTEGER, is_from_me INTEGER, media TEXT,
                PRIMARY KEY (id, chat_id));
            CREATE INDEX IF NOT EXISTS idx_msg_time ON messages(time);
            CREATE INDEX IF NOT EXISTS idx_msg_chat ON messages(chat_id, time);
        """)
        self.db.commit()

    def user_name(self, uid):
        row = self.db.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
        return row[0] if row else None

    def put_user(self, uid, name):
        if uid and name:
            self.db.execute("INSERT OR REPLACE INTO users(id, name) VALUES (?, ?)", (uid, name))

    def put_chat(self, c, title):
        ctype = getattr(c.type, "value", c.type)
        self.db.execute(
            "INSERT INTO chats(id, type, title, participants, last_time) VALUES (?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET type=excluded.type, title=excluded.title, "
            "participants=excluded.participants, last_time=MAX(COALESCE(chats.last_time,0), excluded.last_time)",
            (c.id, str(ctype), title, c.participants_count or len(c.participants or {}), c.last_event_time or 0))

    def put_message(self, m, chat_id, me_id, sender_name):
        media = ",".join(sorted({type(a).__name__ for a in (m.attaches or [])})) or None
        self.db.execute(
            "INSERT OR IGNORE INTO messages(id, chat_id, sender, sender_name, text, time, is_from_me, media) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (m.id, chat_id, m.sender, sender_name, m.text or "", m.time, int(m.sender == me_id), media))
        self.db.execute("UPDATE chats SET last_time=MAX(COALESCE(last_time,0), ?) WHERE id=?", (m.time, chat_id))

    def commit(self):
        self.db.commit()


def user_display(u) -> str | None:
    if u is None:
        return None
    for n in getattr(u, "names", None) or []:
        full = " ".join(filter(None, [n.first_name, n.last_name])) or n.name
        if full:
            return full
    return None


def fmt_time(ms) -> str:
    return dt.datetime.fromtimestamp((ms or 0) / 1000).strftime("%d.%m.%Y %H:%M")


# ---------- вход ----------

class NeedLogin(RuntimeError):
    pass


class RefuseQr:
    """В режиме serve вход не начинаем: только сообщаем, что нужен login."""

    async def show_qr(self, qr_url: str) -> None:
        (STATE / "need-login").write_text("1")
        raise NeedLogin("Вход в MAX не выполнен или слетел. Запусти в терминале команду входа (login).")


class QrOnScreen:
    """Режим login: QR и в терминал, и картинкой в браузере."""

    async def show_qr(self, qr_url: str) -> None:
        import qrcode

        qr = qrcode.QRCode(border=2)
        qr.add_data(qr_url)
        print("\nОтсканируй QR в приложении MAX на телефоне:")
        print("Настройки → Устройства → «Подключить устройство» (или «Сканировать QR-код»)\n")
        qr.print_ascii(invert=True)
        png = STATE / "login-qr.png"
        qrcode.make(qr_url, box_size=10, border=4).save(png)
        with contextlib.suppress(Exception):
            webbrowser.open(png.as_uri())
        print(f"\nЕсли QR в терминале не читается, картинка открыта в браузере: {png}\n")


def make_client(qr_handler, reconnect: bool):
    from pymax import ExtraConfig, QrAuthFlow, WebClient
    from pymax.auth.providers import ConsolePasswordProvider

    STATE.mkdir(parents=True, exist_ok=True)
    return WebClient(
        work_dir=str(STATE), session_name=SESSION,
        auth_flow=QrAuthFlow(qr_handler, password_provider=ConsolePasswordProvider()),
        extra_config=ExtraConfig(log_level="WARNING", reconnect=reconnect, reconnect_delay=10, relogin=False),
    )


async def do_login() -> int:
    (STATE / "need-login").write_text("1")
    client = make_client(QrOnScreen(), reconnect=False)
    done = asyncio.Event()

    @client.on_start()
    async def _start(c):
        name = user_display(getattr(c.me, "contact", None)) or "аккаунт"
        print(f"\nГотово: MAX подключён ({name}). Сессия сохранена в {STATE}.")
        (STATE / "need-login").unlink(missing_ok=True)
        done.set()

    try:
        await asyncio.wait_for(client.connect(), 300)
    except asyncio.TimeoutError:
        print("QR не отсканирован за 5 минут. Запусти вход ещё раз.")
        return 1
    finally:
        with contextlib.suppress(Exception):
            await client.close()
    return 0 if done.is_set() else 1


# ---------- мост внутри MCP ----------

class Bridge:
    def __init__(self):
        STATE.mkdir(parents=True, exist_ok=True)
        self.store = Store(STATE / "messages.db")
        self.client = None
        self.me_id = None
        self.connected = False
        self.error: str | None = None
        self.task: asyncio.Task | None = None

    async def name_of(self, uid):
        if uid is None:
            return None
        cached = self.store.user_name(uid)
        if cached:
            return cached
        try:
            name = user_display(await asyncio.wait_for(self.client.get_user(uid), 20))
        except Exception:  # noqa: BLE001
            name = None
        self.store.put_user(uid, name)
        return name

    async def chat_title(self, c):
        if c.title:
            return c.title
        other = next((uid for uid in (c.participants or {}) if uid != self.me_id), None)
        return await self.name_of(other) or f"chat {c.id}"

    async def save(self, m, chat_id):
        name = "я" if m.sender == self.me_id else await self.name_of(m.sender)
        self.store.put_message(m, chat_id, self.me_id, name)

    async def backfill(self):
        chats = list(self.client.chats or [])
        with contextlib.suppress(Exception):
            chats += await asyncio.wait_for(self.client.fetch_chats(), 60)
        seen = {c.id: c for c in chats}
        ordered = sorted(seen.values(), key=lambda c: c.last_event_time or 0, reverse=True)[:BACKFILL_CHATS]
        for c in ordered:
            try:
                self.store.put_chat(c, await self.chat_title(c))
                if str(getattr(c.type, "value", c.type)).upper() == "CHANNEL":
                    continue
                for m in await asyncio.wait_for(self.client.fetch_history(c.id, backward=BACKFILL_MSGS), 30):
                    await self.save(m, c.id)
                self.store.commit()
                await asyncio.sleep(0.7)  # не долбим сервер MAX
            except Exception as e:  # noqa: BLE001
                LOG.warning("история чата %s: %s", c.id, e)
        self.store.commit()

    def start(self):
        if not (STATE / SESSION).exists():
            self.error = "Вход в MAX ещё не выполнен. Запусти в терминале команду входа (login) и отсканируй QR."
            return
        self.client = make_client(RefuseQr(), reconnect=True)

        @self.client.on_start()
        async def _start(c):
            self.me_id = c.me.contact.id
            self.connected, self.error = True, None
            asyncio.create_task(self.backfill())

        @self.client.on_message()
        async def _msg(m, c):
            try:
                if self.store.db.execute("SELECT 1 FROM chats WHERE id=?", (m.chat_id,)).fetchone() is None:
                    ch = await asyncio.wait_for(c.get_chat(m.chat_id), 20)
                    self.store.put_chat(ch, await self.chat_title(ch))
                await self.save(m, m.chat_id)
                self.store.commit()
            except Exception:  # noqa: BLE001
                LOG.exception("не сохранил сообщение")

        @self.client.on_disconnect()
        async def _disc(exc, reconnect, delay):
            self.connected = False

        async def run():
            try:
                await self.client.start()
            except NeedLogin as e:
                self.error = str(e)
            except Exception as e:  # noqa: BLE001
                self.error = f"MAX не подключился: {e}"
            self.connected = False

        self.task = asyncio.create_task(run())

    async def ready(self, wait: float = 20):
        end = time.monotonic() + wait
        while not self.connected and not self.error and time.monotonic() < end:
            await asyncio.sleep(0.5)
        if not self.connected:
            raise RuntimeError(self.error or "MAX ещё подключается, повтори через минуту.")

    async def stop(self):
        if self.client:
            with contextlib.suppress(Exception):
                await self.client.close()
        if self.task:
            self.task.cancel()
        self.store.commit()


def build_server():
    from contextlib import asynccontextmanager

    from mcp.server.fastmcp import FastMCP

    bridge = Bridge()

    @asynccontextmanager
    async def lifespan(_server):
        bridge.start()
        try:
            yield
        finally:
            await bridge.stop()

    mcp = FastMCP("max", lifespan=lifespan)
    db = bridge.store.db

    def rows(sql, args=()):
        return db.execute(sql, args).fetchall()

    @mcp.tool()
    async def max_status() -> dict:
        """Состояние MAX: подключён ли аккаунт, сколько сообщений сохранено, нужен ли вход."""
        return {"connected": bridge.connected, "error": bridge.error,
                "chats": rows("SELECT COUNT(*) FROM chats")[0][0],
                "messages": rows("SELECT COUNT(*) FROM messages")[0][0],
                "data_dir": str(STATE)}

    @mcp.tool()
    async def max_list_chats(query: str = "", limit: int = 30) -> list[dict]:
        """Чаты MAX, свежие сверху. query фильтрует по названию или имени собеседника."""
        with contextlib.suppress(Exception):
            await bridge.ready(5)
        out = rows("SELECT id, type, title, participants, last_time FROM chats WHERE title LIKE ? "
                   "ORDER BY last_time DESC LIMIT ?", (f"%{query}%", limit))
        return [{"chat_id": r[0], "type": r[1], "title": r[2], "participants": r[3], "last": fmt_time(r[4])}
                for r in out]

    @mcp.tool()
    async def max_get_messages(chat_id: int, count: int = 50) -> list[dict]:
        """Последние сообщения чата MAX прямо с сервера (свежие снизу). chat_id брать из max_list_chats."""
        await bridge.ready()
        got = await asyncio.wait_for(bridge.client.fetch_history(chat_id, backward=min(count, 200)), 60)
        for m in got:
            await bridge.save(m, chat_id)
        bridge.store.commit()
        out = []
        for m in sorted(got, key=lambda m: m.time or 0):
            who = "я" if m.sender == bridge.me_id else await bridge.name_of(m.sender)
            media = ",".join(sorted({type(a).__name__ for a in (m.attaches or [])}))
            out.append({"id": m.id, "time": fmt_time(m.time), "from": who, "text": m.text or "",
                        **({"media": media} if media else {})})
        return out

    @mcp.tool()
    async def max_search_messages(query: str, chat_id: int | None = None, limit: int = 50) -> list[dict]:
        """Поиск по тексту среди сохранённых сообщений MAX (свежие чаты подтягиваются при запуске)."""
        sql = ("SELECT m.id, m.chat_id, c.title, m.sender_name, m.text, m.time FROM messages m "
               "LEFT JOIN chats c ON c.id=m.chat_id WHERE m.text LIKE ?")
        args: list = [f"%{query}%"]
        if chat_id is not None:
            sql += " AND m.chat_id=?"
            args.append(chat_id)
        sql += " ORDER BY m.time DESC LIMIT ?"
        args.append(limit)
        return [{"id": r[0], "chat_id": r[1], "chat": r[2], "from": r[3], "text": r[4], "time": fmt_time(r[5])}
                for r in rows(sql, args)]

    @mcp.tool()
    async def max_send_message(chat_id: int, text: str) -> dict:
        """Отправить сообщение в MAX от имени владельца аккаунта.
        ВАЖНО: сначала покажи пользователю точный текст и получателя, отправляй только после его явного «да/ок»."""
        await bridge.ready()
        if not text.strip():
            raise ValueError("пустой текст")
        m = await asyncio.wait_for(bridge.client.send_message(chat_id, text), 30)
        if m is not None:
            await bridge.save(m, chat_id)
            bridge.store.commit()
        return {"ok": True, "message_id": getattr(m, "id", None)}

    return mcp


def main():
    p = argparse.ArgumentParser(description="MAX для Claude Code (NEOVIDA)")
    p.add_argument("command", choices=["serve", "login", "status"])
    a = p.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", line_buffering=True)
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    STATE.mkdir(parents=True, exist_ok=True)
    if a.command == "login":
        sys.exit(asyncio.run(do_login()))
    if a.command == "status":
        ok = (STATE / SESSION).exists() and not (STATE / "need-login").exists()
        print(json.dumps({"logged_in": ok, "data_dir": str(STATE)}, ensure_ascii=False))
        sys.exit(0 if ok else 1)
    build_server().run()


if __name__ == "__main__":
    main()
