#!/usr/bin/env python3
"""
crawlbot_monitor.py — Standalone Python watcher for
crawlbot_portable_scheduler_headless_server_v1

Replaces OpenClaw cronjobs:
  1. Immediate error watchdog (every 60s)
  2. Hourly status report (every 3600s)

Runs as a daemon. Sends alerts/reports directly via Telegram Bot API.
Zero OpenClaw token consumed.
"""

import asyncio
import os
import re
import stat
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_DIR / ".env"
STATE_FILE = REPO_DIR / "logs" / "forensic-watch.state"
LOGS_DIR = REPO_DIR / "logs"

# Parse .env (simple key=value, no expansion needed for our keys)
def _load_env(path: Path) -> dict[str, str]:
    cfg: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.strip()
    return cfg

env = _load_env(ENV_FILE)
TELEGRAM_TOKEN = env.get("TELEGRAM_TOKEN", "")
ADMIN_CHAT_ID = env.get("ADMIN_CHAT_ID", "2079315704")
ALERT_CHAT_ID = env.get("ALERT_CHAT_ID", ADMIN_CHAT_ID)

# Forensic error patterns (mirrors bash script)
FORENSIC_PATTERN = re.compile(
    r"tab crashed|read timed out|HTTPConnectionPool|BROWSER_FATAL|"
    r"BROWSER_RECOVERY|BROWSER_RECOVERY_ESCALATION|browser_fatal|"
    r"browser_recovery|CRASH DIAGNOSTICS|Traceback \(most recent call last\)|"
    r"selenium\.common\.exceptions\.WebDriverException|ERR_TAB_CRASHED|"
    r"ERR_DRIVER_TIMEOUT|driver_timeout_suspected|browser_disconnect|"
    r"unknown_browser_fatal|invalid session id|"
    r"classify_browser_error is not defined",
    re.IGNORECASE,
)

WATCHDOG_INTERVAL = 60   # seconds
REPORT_INTERVAL = 3600   # seconds
DEDUP_WINDOW = 180       # seconds

# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------

def tg_api(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"


def tg_escape(text: str) -> str:
    """Escape text for MarkdownV2."""
    return re.sub(r'([_\*\[\]\(\)~`>#+\-=\{\}\.\!])', r'\\\1', text)


async def tg_send(chat_id: str, text: str, parse_mode: str = "MarkdownV2") -> bool:
    """Send a Telegram message. Retries up to 3 times with backoff."""
    url = tg_api("sendMessage")
    payload = (
        f"chat_id={quote(chat_id)}"
        f"&text={quote(text)}"
        f"&parse_mode={quote(parse_mode)}"
        f"&disable_web_page_preview=true"
    )
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(
                url,
                data=payload.encode(),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode()
                if resp.status == 200:
                    # Could parse JSON, but 200 is sufficient signal
                    return True
        except Exception as e:
            wait = attempt * 2
            await asyncio.sleep(wait)
    return False


# ---------------------------------------------------------------------------
# Log discovery
# ---------------------------------------------------------------------------

def latest_log() -> Path | None:
    """Return the most recently modified .log in logs/."""
    best = None
    best_mtime = 0.0
    try:
        for f in LOGS_DIR.iterdir():
            if f.is_file() and f.suffix == ".log":
                mt = f.stat().st_mtime
                if mt > best_mtime:
                    best_mtime = mt
                    best = f
    except Exception:
        pass
    return best


# ---------------------------------------------------------------------------
# State persistence (inode + offset dedup)
# ---------------------------------------------------------------------------

def _read_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    state = {}
    try:
        for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                state[k.strip()] = v.strip()
    except Exception:
        pass
    return state


def _write_state(**kw):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        for k, v in kw.items():
            f.write(f"{k}={v}\n")


# ---------------------------------------------------------------------------
# Watchdog: check for new forensic markers
# ---------------------------------------------------------------------------

async def check_forensic_once() -> None:
    """One scan of new log lines for forensic markers."""
    log_file = latest_log()
    if log_file is None:
        print("[watchdog] no log file found")
        return

    s = log_file.stat()
    current_inode = s.st_ino
    current_size = s.st_size

    old = _read_state()
    last_inode = old.get("last_inode", "")
    last_offset = int(old.get("last_offset", "0"))
    last_key = old.get("last_key", "")
    last_ts = int(old.get("last_ts", "0"))

    # Reset if inode changed or log rotated (truncated)
    if str(current_inode) != last_inode or current_size < last_offset:
        last_offset = 0

    start_byte = last_offset
    if start_byte >= current_size:
        print("[watchdog] no new data")
        return

    # Read new bytes
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            f.seek(start_byte)
            chunk = f.read()
    except Exception as e:
        print(f"[watchdog] read error: {e}")
        return

    new_offset = current_size

    matches = FORENSIC_PATTERN.findall(chunk)
    if not matches:
        _write_state(
            last_inode=current_inode,
            last_offset=new_offset,
            last_key="",
            last_ts=last_ts,
        )
        return

    # Build alert_key for dedup
    # Grab the last matching line
    match_lines = [
        line for line in chunk.splitlines() if FORENSIC_PATTERN.search(line)
    ]
    if not match_lines:
        return
    last_match_line = match_lines[-1]
    alert_key = last_match_line[:300].strip()

    now = int(time.time())

    # Dedup: same key within window -> skip
    if alert_key == last_key and (now - last_ts) < DEDUP_WINDOW:
        _write_state(
            last_inode=current_inode,
            last_offset=new_offset,
            last_key=alert_key,
            last_ts=now,
        )
        return

    match_count = len(match_lines)

    # Build context: last 60 lines of log
    try:
        context_text = log_file.read_text(encoding="utf-8", errors="replace")
        context_lines = context_text.splitlines()[-60:]
        context = "\n".join(context_lines)[-2600:]
    except Exception:
        context = "<unable to read context>"

    # Format Telegram alert (MarkdownV2)
    ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alert_msg = (
        f"🚨 *Crawlbot Alert*\n\n"
        f"📅 {tg_escape(ts_str)}\n"
        f"🔢 Matches: {match_count}\n"
        f"📄 Last match: {tg_escape(last_match_line[:200])}\n\n"
        f"*Context:*\n"
        f"```{tg_escape(context)}```"
    )

    ok = await tg_send(ALERT_CHAT_ID, alert_msg)
    if ok:
        print(f"[watchdog] alert sent ({match_count} matches)")
    else:
        print("[watchdog] FAILED to send alert after retries")

    # Also notify admin directly
    if str(ALERT_CHAT_ID) != str(ADMIN_CHAT_ID):
        short_msg = (
            f"🚨 Crawlbot Alert — {match_count} match\\(es\\)\n"
            f"📄 {tg_escape(last_match_line[:250])}"
        )
        await tg_send(ADMIN_CHAT_ID, short_msg)

    _write_state(
        last_inode=current_inode,
        last_offset=new_offset,
        last_key=alert_key,
        last_ts=now,
    )


# ---------------------------------------------------------------------------
# Hourly status report
# ---------------------------------------------------------------------------

def _find_crawler_pid() -> str:
    """Find the main.py process running in REPO_DIR."""
    repo = str(REPO_DIR)
    try:
        # List /proc/*/cwd and /proc/*/cmdline
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                cwd = os.readlink(str(entry / "cwd"))
                cmd = (entry / "cmdline").read_bytes().replace(
                    b"\x00", b" "
                ).decode("utf-8", "ignore")
            except Exception:
                continue
            if cwd == repo and "python" in cmd and "main.py" in cmd:
                return entry.name
    except Exception:
        pass
    # Fallback: try shell pidof-style
    try:
        out = subprocess.run(
            ["pgrep", "-f", f"python.*main.py"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip().split()[0]
    except Exception:
        pass
    return ""


def _get_process_info(pid: str) -> str:
    if not pid:
        return "crawler: not running"
    try:
        out = subprocess.run(
            ["ps", "-o", "etime=,stat=", "-p", pid],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            parts = out.stdout.strip().split()
            etime = parts[0]
            st = parts[1] if len(parts) > 1 else "?"
            return f"crawler: pid={pid} up since={etime} stat={st}"
    except Exception:
        pass
    return f"crawler: pid={pid} (status unknown)"


async def hourly_report() -> None:
    """Generate and send hourly status report."""
    log_file = latest_log()
    ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Process status
    pid = _find_crawler_pid()
    proc_info = _get_process_info(pid)

    # Parse log for key markers
    last_nav = "<none>"
    last_room_switch = "<none>"
    last_forensic = "<none>"

    if log_file and log_file.exists():
        try:
            text = log_file.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()

            nav_lines = [
                l for l in lines if "Navigation ok; verify_mode=" in l
            ]
            if nav_lines:
                last_nav = nav_lines[-1]

            room_lines = [
                l for l in lines if "ROOM_SWITCH_TRACKER" in l
            ]
            if room_lines:
                last_room_switch = room_lines[-1]

            forensic_lines = [
                l for l in lines if FORENSIC_PATTERN.search(l)
            ]
            if forensic_lines:
                last_forensic = "\n".join(forensic_lines[-5:])
        except Exception:
            pass

    # Build report (MarkdownV2)
    report = (
        f"🦋 *Crawlbot Hourly Status*\n\n"
        f"📅 {tg_escape(ts_str)}\n"
        f"📂 {tg_escape(str(REPO_DIR))}\n"
        f"📄 {tg_escape(str(log_file) if log_file else '<none>')}\n"
        f"🔧 {tg_escape(proc_info)}\n\n"
        f"*Navigation ok:*\n"
        f"```{tg_escape(last_nav[:200])}```\n\n"
        f"*Room switch:*\n"
        f"```{tg_escape(last_room_switch[:200])}```\n\n"
        f"*Forensic markers (last 5):*\n"
        f"```{tg_escape(last_forensic[:400])}```"
    )

    ok = await tg_send(ADMIN_CHAT_ID, report)
    if ok:
        print("[hourly] status sent")
    else:
        print("[hourly] FAILED to send status after retries")


# ---------------------------------------------------------------------------
# Bootstrap: test Telegram connectivity
# ---------------------------------------------------------------------------

async def test_telegram() -> bool:
    """Send a test message to confirm bot works."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_msg = (
        f"✅ *Crawlbot Monitor Online*\n\n"
        f"📅 {tg_escape(ts)}\n"
        f"Repository: {tg_escape(str(REPO_DIR))}\n"
        f"Watchdog interval: {WATCHDOG_INTERVAL}s\n"
        f"Report interval: {REPORT_INTERVAL}s\n\n"
        f"_Replaces OpenClaw cronjobs — zero token cost\\._"
    )
    return await tg_send(ADMIN_CHAT_ID, test_msg)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def main():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[monitor] starting at {datetime.now().isoformat()}")
    print(f"[monitor] repo: {REPO_DIR}")
    print(f"[monitor] admin chat: {ADMIN_CHAT_ID}")
    print(f"[monitor] alert chat: {ALERT_CHAT_ID}")

    # Test Telegram on startup
    if not TELEGRAM_TOKEN:
        print("[monitor] ERROR: TELEGRAM_TOKEN not set in .env")
        sys.exit(1)

    ok = await test_telegram()
    if not ok:
        print("[monitor] WARNING: Telegram test message failed")
    else:
        print("[monitor] Telegram connectivity OK")

    next_report = time.time() + REPORT_INTERVAL

    while True:
        # Watchdog tick
        try:
            await check_forensic_once()
        except Exception as e:
            print(f"[watchdog] error: {e}")

        # Hourly report tick
        now = time.time()
        if now >= next_report:
            try:
                await hourly_report()
            except Exception as e:
                print(f"[hourly] error: {e}")
            next_report = now + REPORT_INTERVAL

        await asyncio.sleep(WATCHDOG_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[monitor] stopped by user")
    except Exception as e:
        print(f"[monitor] FATAL: {e}")
        sys.exit(1)
