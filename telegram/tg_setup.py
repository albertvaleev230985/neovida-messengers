"""Telegram для агента без ручных шагов ученика.

Агент (Codex или Claude) запускает команды сам. От человека нужны только номер телефона,
два кода, которые Telegram пришлёт в само приложение Telegram, и облачный пароль, если он включён
(пароль вводится в отдельном окошке на компьютере и в чат не попадает).

Запуск из окружения плагина, чтобы были telethon и codex_telegram:
  uv run --project ~/.neovida-messengers/telegram-plugin/telegram/mcp_server python tg_setup.py <команда>

Команды по порядку:
  keys-send   --phone +79991234567   отправить код для my.telegram.org (придёт в Telegram)
  keys-finish --code 12345           войти на my.telegram.org, взять или создать приложение, сохранить api_id и api_hash
  login-send                         отправить код входа в Telegram (придёт в Telegram)
  login-finish --code 12345          войти; облачный пароль спросит окошком
  status                             что уже сделано
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import random
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

HOME = Path(os.environ.get("NEOVIDA_MESSENGERS_HOME", Path.home() / ".neovida-messengers")) / "telegram"
STATE = HOME / "state.json"
API = HOME / "api.json"
COOKIES = HOME / "my_telegram_cookies.txt"
MY = "https://my.telegram.org"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


def _private_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _say(ok: bool, text: str, **extra) -> None:
    print(json.dumps({"ok": ok, "message": text, **extra}, ensure_ascii=False))
    if not ok:
        sys.exit(1)


def _phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if len(digits) < 10:
        _say(False, "Номер слишком короткий. Нужен полный номер, например +79991234567.")
    return "+" + digits


# ---------------------------------------------------------------- my.telegram.org

def _curl() -> str:
    exe = shutil.which("curl.exe") or shutil.which("curl")
    if not exe:
        _say(False, "Нет curl. На Windows 10 и 11 он встроен, на Mac тоже. Обновите систему или поставьте curl.")
    return exe


def _request(path: str, data: dict | None = None) -> tuple[int, str]:
    """Запрос к my.telegram.org через системный curl: он берёт сертификаты системы и работает за VPN и прокси."""
    HOME.mkdir(parents=True, exist_ok=True)
    cmd = [_curl(), "-s", "-L", "--max-time", "30", "-A", UA, "-H", "X-Requested-With: XMLHttpRequest",
           "-H", f"Origin: {MY}", "-H", f"Referer: {MY}/auth", "-b", str(COOKIES), "-c", str(COOKIES),
           "-w", "\n__STATUS__%{http_code}"]
    if data is not None:
        cmd += ["--data-binary", "@-"]
    r = subprocess.run(cmd + [MY + path], input=urllib.parse.urlencode(data or {}).encode() if data is not None else None,
                       capture_output=True)
    out = r.stdout.decode("utf-8", "replace")
    body, _, status = out.rpartition("\n__STATUS__")
    try:
        os.chmod(COOKIES, 0o600)
    except OSError:
        pass
    return (int(status) if status.strip().isdigit() else 0), body


def parse_apps(page: str) -> tuple[int | None, str | None]:
    """api_id и api_hash со страницы /apps. Пусто, если приложения ещё нет."""
    api_id = api_hash = None
    i = page.find("api_id")
    if i >= 0:
        m = re.search(r"<strong>\s*(\d{4,})\s*</strong>", page[i:i + 600]) or re.search(r">\s*(\d{4,})\s*<", page[i:i + 600])
        if m:
            api_id = int(m.group(1))
    j = page.find("api_hash")
    if j >= 0:
        m = re.search(r"\b([0-9a-f]{32})\b", page[j:j + 600])
        if m:
            api_hash = m.group(1)
    return api_id, api_hash


def parse_create_hash(page: str) -> str | None:
    m = re.search(r'name="hash"\s+value="([^"]+)"', page) or re.search(r'value="([^"]+)"\s+name="hash"', page)
    return html.unescape(m.group(1)) if m else None


def keys_send(phone: str) -> None:
    phone = _phone(phone)
    if COOKIES.exists():
        COOKIES.unlink()
    code, text = _request("/auth/send_password", {"phone": phone})
    try:
        random_hash = json.loads(text)["random_hash"]
    except (ValueError, KeyError, TypeError):
        _say(False, f"my.telegram.org не принял номер: {text.strip()[:200]}. Если написано про слишком много попыток, подождите час. "
                    "Если ошибка непонятная, выключите VPN и повторите keys-send.")
    state = _read(STATE)
    state.update({"phone": phone, "random_hash": random_hash})
    _private_write(STATE, state)
    _say(True, "Код отправлен. Он пришёл в приложение Telegram (сообщение от «Telegram», не СМС). "
               "Попросите человека прислать этот код и запустите keys-finish --code <код>.")


def keys_finish(code_value: str) -> None:
    state = _read(STATE)
    if not state.get("random_hash"):
        _say(False, "Сначала keys-send --phone <номер>.")
    status, text = _request("/auth/login", {"phone": state["phone"], "random_hash": state["random_hash"],
                                                "password": code_value.strip(), "remember": "1"})
    if status != 200 or "true" not in text.lower():
        _say(False, f"Код не подошёл: {text.strip()[:200]}. Попросите свежий код: снова keys-send.")
    _, page = _request("/apps")
    api_id, api_hash = parse_apps(page)
    created = False
    if not (api_id and api_hash):
        form_hash = parse_create_hash(page)
        if not form_hash:
            _say(False, "Не нашёл форму создания приложения на my.telegram.org/apps. Откройте страницу в браузере и проверьте вход.")
        for attempt in range(3):
            short = f"codexagent{random.randint(10000, 99999)}"
            status, text = _request("/apps/create", {"hash": form_hash, "app_title": "Codex Assistant",
                                                          "app_shortname": short, "app_url": "", "app_platform": "desktop",
                                                          "app_desc": ""})
            _, page = _request("/apps")
            api_id, api_hash = parse_apps(page)
            if api_id and api_hash:
                created = True
                break
        if not (api_id and api_hash):
            _say(False, f"my.telegram.org не дал создать приложение ({text.strip()[:80] or 'ERROR'}). Частая причина: VPN или браузерная блокировка. "
                        "Выключите VPN и повторите keys-send и keys-finish.")
    _private_write(API, {"api_id": api_id, "api_hash": api_hash, "phone": state["phone"]})
    _say(True, ("Создал приложение и сохранил ключи." if created else "Приложение уже было, ключи сохранены.") +
         " Дальше login-send.", api_id=api_id, api_hash_tail="…" + api_hash[-4:])


# ---------------------------------------------------------------- вход в Telegram

def _need_plugin():
    try:
        from codex_telegram.auth import _build_client  # noqa: F401
        from codex_telegram.models import StoredSession  # noqa: F401
    except ImportError:
        _say(False, "Запускайте через uv run --project <папка плагина>/telegram/mcp_server, иначе нет telethon и codex_telegram.")


def _ask_password() -> str | None:
    """Облачный пароль окошком на компьютере человека, чтобы он не уходил в чат."""
    env = os.environ.get("TG_2FA_PASSWORD")
    if env:
        return env
    try:
        import tkinter
        from tkinter import simpledialog
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        value = simpledialog.askstring("Telegram", "Облачный пароль Telegram\n(он не уйдёт в чат)", show="*", parent=root)
        root.destroy()
        return value
    except Exception:
        return None


async def _login_send() -> None:
    _need_plugin()
    from telethon.sessions import StringSession
    from codex_telegram.auth import _build_client
    api = _read(API)
    if not api.get("api_id"):
        _say(False, "Сначала ключи: keys-send и keys-finish.")
    from telethon import errors
    client = _build_client(StringSession(), api["api_id"], api["api_hash"])
    await client.connect()
    try:
        sent = await client.send_code_request(api["phone"])
        state = _read(STATE)
        state.update({"login_session": StringSession.save(client.session), "phone_code_hash": sent.phone_code_hash})
        _private_write(STATE, state)
    except errors.ApiIdInvalidError:
        _say(False, "Telegram не принял api_id и api_hash. Получите ключи заново: keys-send и keys-finish.")
    except (errors.PhoneNumberInvalidError, errors.PhoneNumberBannedError) as exc:
        _say(False, f"Telegram не принял номер: {exc}. Проверьте номер и запустите keys-send заново.")
    except errors.FloodWaitError as exc:
        _say(False, f"Telegram просит подождать {exc.seconds} секунд перед новой попыткой. Подождите и повторите login-send.")
    finally:
        await client.disconnect()
    _say(True, "Код входа отправлен в приложение Telegram. Попросите человека прислать его и запустите login-finish --code <код>.")


async def _login_finish(code_value: str) -> None:
    _need_plugin()
    from telethon import errors, utils as tg_utils
    from telethon.sessions import StringSession
    from codex_telegram.auth import _build_client
    from codex_telegram.helpers import utc_now
    from codex_telegram.models import StoredSession
    from codex_telegram.session_store import save_session
    api, state = _read(API), _read(STATE)
    if not state.get("login_session"):
        _say(False, "Сначала login-send.")
    client = _build_client(StringSession(state["login_session"]), api["api_id"], api["api_hash"])
    await client.connect()
    try:
        try:
            await client.sign_in(phone=api["phone"], code=code_value.strip(), phone_code_hash=state["phone_code_hash"])
        except errors.SessionPasswordNeededError:
            password = _ask_password()
            if not password:
                _say(False, "Нужен облачный пароль Telegram, а окошко не открылось. Запустите login-finish ещё раз "
                            "или передайте пароль переменной TG_2FA_PASSWORD, не печатая его в чат.")
            await client.sign_in(password=password)
        me = await client.get_me()
        now = utc_now().isoformat()
        record = StoredSession(api_id=api["api_id"], api_hash=api["api_hash"], session_string=StringSession.save(client.session),
                               phone=api["phone"], user_id=me.id, username=getattr(me, "username", None),
                               display_name=tg_utils.get_display_name(me), created_at=now, updated_at=now)
        backend = save_session(record, prompt_if_missing=False)
    except (errors.PhoneCodeInvalidError, errors.PhoneCodeExpiredError):
        _say(False, "Код не подошёл или устарел. Запустите login-send ещё раз и попросите свежий код.")
    except errors.PasswordHashInvalidError:
        _say(False, "Облачный пароль неверный. Запустите login-finish с тем же кодом ещё раз.")
    finally:
        await client.disconnect()
    for key in ("login_session", "phone_code_hash", "random_hash"):
        state.pop(key, None)
    _private_write(STATE, state)
    _say(True, f"Telegram подключён: {record.display_name}. Сессия сохранена ({backend}). Перезапустите приложение агента.",
         user_ref=f"user:{record.user_id}")


def status() -> None:
    api, state = _read(API), _read(STATE)
    _say(True, "Состояние", keys=bool(api.get("api_id")), phone=api.get("phone") or state.get("phone"),
         waiting_login_code=bool(state.get("login_session")), waiting_keys_code=bool(state.get("random_hash")))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keys-send").add_argument("--phone", required=True)
    sub.add_parser("keys-finish").add_argument("--code", required=True)
    sub.add_parser("login-send")
    sub.add_parser("login-finish").add_argument("--code", required=True)
    sub.add_parser("status")
    a = p.parse_args()
    if a.cmd == "keys-send":
        keys_send(a.phone)
    elif a.cmd == "keys-finish":
        keys_finish(a.code)
    elif a.cmd == "login-send":
        asyncio.run(_login_send())
    elif a.cmd == "login-finish":
        asyncio.run(_login_finish(a.code))
    else:
        status()


if __name__ == "__main__":
    main()
