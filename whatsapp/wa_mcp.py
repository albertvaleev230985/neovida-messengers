# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "whatsapp-mcp-server @ https://github.com/verygoodplugins/whatsapp-mcp/releases/download/v0.7.0/whatsapp_mcp_server-0.7.0-py3-none-any.whl",
#     "qrcode[pil]>=7.4",
# ]
# ///
"""WhatsApp для Claude Code: мост whatsmeow + MCP, всё на компьютере ученика.

Та же схема, что у Альберта на сервере Гермеса (verygoodplugins/whatsapp-mcp v0.7.0
плюс наш патч «вход по коду вместо QR»), только локально:
- `uv run --script wa_mcp.py login [--phone 79991234567]`  привязка к телефону
- `uv run --script wa_mcp.py serve`   MCP по stdio; его запускает Claude Code,
  он же сам поднимает мост в фоне, если тот не запущен
- `uv run --script wa_mcp.py status`  проверка
- `uv run --script wa_mcp.py stop`    остановить мост

Мост скачивается один раз из релиза neovida-messengers под вашу систему.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

HOME = Path(os.environ.get("NEOVIDA_WA_DIR", Path.home() / ".neovida-messengers" / "whatsapp"))
STORE = HOME / "store"
PORT = int(os.environ.get("NEOVIDA_WA_PORT", "18081"))
RELEASE = "https://github.com/albertvaleev230985/neovida-messengers/releases/download/v1.0"
IS_WIN = os.name == "nt"
BIN = HOME / ("whatsapp-bridge.exe" if IS_WIN else "whatsapp-bridge")
PIDFILE = HOME / "bridge.pid"
LOGFILE = HOME / "bridge.log"


def err(*a):
    print(*a, file=sys.stderr, flush=True)


def asset_name() -> str:
    mach = platform.machine().lower()
    if IS_WIN:
        return "whatsapp-bridge-windows-amd64.exe"
    if sys.platform == "darwin":
        return "whatsapp-bridge-macos-arm64" if mach in ("arm64", "aarch64") else "whatsapp-bridge-macos-amd64"
    raise SystemExit("Поддерживаются macOS и Windows.")


def ensure_binary():
    if BIN.exists():
        return
    HOME.mkdir(parents=True, exist_ok=True)
    url = f"{RELEASE}/{asset_name()}"
    err(f"Скачиваю мост WhatsApp: {url}")
    tmp = BIN.with_suffix(".download")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(BIN)
    if not IS_WIN:
        BIN.chmod(0o755)


def paired() -> bool:
    """Привязка есть, если в базе whatsmeow записано устройство."""
    import sqlite3

    db = STORE / "whatsapp.db"
    if not db.exists():
        return False
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
            return c.execute("SELECT COUNT(*) FROM whatsmeow_device").fetchone()[0] > 0
    except sqlite3.Error:
        return False


def port_open() -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def pid_alive(pid: int) -> bool:
    if IS_WIN:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def running_pid() -> int | None:
    try:
        pid = int(PIDFILE.read_text().strip())
    except (OSError, ValueError):
        return None
    return pid if pid_alive(pid) else None


def spawn_bridge(phone: str | None = None) -> int:
    ensure_binary()
    STORE.mkdir(parents=True, exist_ok=True)
    env = os.environ | {
        "WHATSAPP_BRIDGE_PORT": str(PORT),
        "WHATSAPP_DEVICE_NAME": "Claude Code (NEOVIDA)",
        "WEBHOOK_ENABLED": "false",
        "WHATSAPP_MEDIA_ROOTS": str(HOME / "outbox"),
    }
    (HOME / "outbox").mkdir(exist_ok=True)
    args = [str(BIN)] + (["--pair-phone", phone] if phone else [])
    kw: dict = {"cwd": HOME, "env": env, "stdin": subprocess.DEVNULL,
                "stdout": open(LOGFILE, "ab"), "stderr": subprocess.STDOUT}
    if IS_WIN:
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen(args, **kw)
    PIDFILE.write_text(str(p.pid))
    return p.pid


def stop_bridge():
    pid = running_pid()
    if not pid:
        return False
    if IS_WIN:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        os.kill(pid, 15)
    for _ in range(20):
        if not pid_alive(pid):
            break
        time.sleep(0.5)
    PIDFILE.unlink(missing_ok=True)
    return True


def show_qr_page(code: str, pair_code: str | None):
    import qrcode

    png = HOME / "login-qr.png"
    qrcode.make(code, box_size=10, border=4).save(png)
    extra = (f"<p style='font-size:28px'>Или код: <b style='letter-spacing:4px'>{pair_code}</b><br>"
             "<small>WhatsApp → Связанные устройства → Привязка устройства → «Связать по номеру телефона»</small></p>"
             if pair_code else "")
    page = HOME / "login.html"
    page.write_text(
        "<html><head><meta charset='utf-8'><meta http-equiv='refresh' content='5'>"
        "<title>WhatsApp → Claude</title></head><body style='font-family:sans-serif;text-align:center'>"
        "<h2>Отсканируйте QR в WhatsApp на телефоне</h2>"
        "<p>WhatsApp → Настройки → Связанные устройства → Привязка устройства</p>"
        f"<img src='login-qr.png?{int(time.time())}' width='360'>{extra}"
        "<p><small>Страница обновляется сама: QR меняется каждые ~20 секунд.</small></p></body></html>",
        encoding="utf-8")
    return page


def do_login(phone: str | None) -> int:
    if paired():
        ensure_running()
        print("WhatsApp уже привязан, мост " + ("работает." if port_open() else f"не поднялся, смотрите {LOGFILE}"))
        return 0
    stop_bridge()
    for f in ("qr.txt", "pair-code.txt"):
        (STORE / f).unlink(missing_ok=True)
    pid = spawn_bridge(phone)
    print("Мост запущен, жду QR от WhatsApp (нужен VPN, если WhatsApp у вас работает только через него)...")
    opened, last = False, None
    deadline = time.time() + 600
    while time.time() < deadline:
        if not pid_alive(pid):
            print(f"Мост остановился. Лог: {LOGFILE}")
            return 1
        if paired() and port_open():
            print("\nГотово: WhatsApp привязан. Мост работает в фоне, история подтягивается с телефона.")
            return 0
        qr = STORE / "qr.txt"
        if qr.exists():
            code = qr.read_text().strip()
            pc = (STORE / "pair-code.txt").read_text().strip() if (STORE / "pair-code.txt").exists() else None
            if code and code != last:
                last = code
                page = show_qr_page(code, pc)
                if pc:
                    print(f"\nКод для входа по номеру: {pc}")
                if not opened:
                    webbrowser.open(page.as_uri())
                    opened = True
                    print(f"QR открыт в браузере: {page}")
        time.sleep(2)
    print("За 10 минут привязка не случилась. Запустите вход ещё раз.")
    stop_bridge()
    return 1


def ensure_running():
    if not paired():
        err("WhatsApp ещё не привязан: запустите вход (login).")
        return
    if port_open():
        return
    if not running_pid():
        spawn_bridge()
    for _ in range(30):
        if port_open():
            return
        time.sleep(1)
    err(f"Мост WhatsApp не поднялся за 30 секунд, смотрите {LOGFILE}")


def serve():
    ensure_running()
    os.environ.update({
        "WHATSAPP_DB_PATH": str(STORE / "messages.db"),
        "WHATSMEOW_DB_PATH": str(STORE / "whatsapp.db"),
        "WHATSAPP_API_URL": f"http://127.0.0.1:{PORT}/api",
        "WHATSAPP_MEDIA_ROOTS": str(HOME / "outbox"),
        "WHATSAPP_MCP_TRANSPORT": "stdio",
    })
    import runpy

    sys.argv = ["main"]
    runpy.run_module("main", run_name="__main__")


def main():
    p = argparse.ArgumentParser(description="WhatsApp для Claude Code (NEOVIDA)")
    p.add_argument("command", choices=["serve", "login", "status", "stop"])
    p.add_argument("--phone", help="номер для входа кодом, только цифры: 79991234567")
    a = p.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", line_buffering=True)
    HOME.mkdir(parents=True, exist_ok=True)
    if a.command == "login":
        sys.exit(do_login(a.phone))
    if a.command == "stop":
        print("остановлен" if stop_bridge() else "мост не был запущен")
        return
    if a.command == "status":
        st = {"paired": paired(), "bridge_pid": running_pid(),
              "api_up": port_open(), "dir": str(HOME)}
        print(json.dumps(st, ensure_ascii=False))
        sys.exit(0 if st["api_up"] else 1)
    serve()


if __name__ == "__main__":
    main()
