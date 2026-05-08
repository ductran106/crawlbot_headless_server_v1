#!/usr/bin/env python3
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

ROOT = Path('/home/farm4bot/work/crawlbot_portable_scheduler_Final_v1')
LOG_DIR = ROOT / 'logs'
ERR_DIR = ROOT / 'data' / 'logs' / 'errors'
BAD_PATTERNS = [
    r'ERROR - Lỗi khi tìm kiếm nhóm',
    r'HTTPConnectionPool\(',
    r'Read timed out',
    r'tab crashed',
    r'group-opened-unverified',
]
SOFT_PATTERNS = [
    r'group-opened-usable-unverified',
    r'navigation-stall',
    r'verify_mode=',
    r'ROOM_SWITCH_TRACKER',
    r'fairness scheduler:',
]

def sh(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, text=True, capture_output=True).stdout.strip()


def list_recent_logs(limit=6, max_age_hours=8) -> List[Path]:
    if not LOG_DIR.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    files = []
    for p in LOG_DIR.rglob('*'):
        if not p.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
        except Exception:
            continue
        if mtime >= cutoff:
            files.append(p)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def tail_lines(path: Path, n=300) -> List[str]:
    try:
        with path.open('r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        return lines[-n:]
    except Exception:
        return []


def grep_patterns(lines: List[str], patterns: List[str]) -> List[str]:
    out = []
    regs = [re.compile(p) for p in patterns]
    for line in lines:
        if any(r.search(line) for r in regs):
            out.append(line.rstrip())
    return out


def process_running() -> bool:
    cmd = r"ps -eo cmd | grep -E '[r]un-gui-session\.sh|[.]venv/bin/python main\.py|[p]ython main\.py' >/dev/null && echo yes || echo no"
    return sh(cmd).strip() == 'yes'


def latest_session_log() -> Path | None:
    logs = list_recent_logs(limit=10)
    for p in logs:
        if p.name.startswith('20') and p.suffix == '.log':
            return p
    for p in logs:
        if p.name == 'run-gui-session-watch.log':
            return p
    return logs[0] if logs else None


def summarize() -> Dict[str, Any]:
    recent_logs = list_recent_logs(limit=8)
    all_bad = []
    all_soft = []
    latest = latest_session_log()
    latest_tail = tail_lines(latest, 400) if latest else []

    for p in recent_logs:
        lines = tail_lines(p, 250)
        bad = grep_patterns(lines, BAD_PATTERNS)
        soft = grep_patterns(lines, SOFT_PATTERNS)
        if bad:
            all_bad.extend([f'[{p.name}] {x}' for x in bad[-20:]])
        if soft:
            all_soft.extend([f'[{p.name}] {x}' for x in soft[-40:]])

    room_switch_ok = any('ROOM_SWITCH_TRACKER' in x for x in latest_tail[-200:])
    fairness_ok = any('fairness scheduler:' in x for x in latest_tail[-200:])
    verify_mode_hits = [x for x in all_soft if 'verify_mode=' in x or 'group-opened-usable-unverified' in x or 'navigation-stall' in x]
    hard_regressions = [x for x in all_bad if not ('shutdown-in-progress' in x and 'crawlbot_control_button' in ''.join(latest_tail[-80:]))]

    late_issues = []
    for line in latest_tail[-120:]:
        if 'shutdown-in-progress' in line:
            if 'crawlbot_control_button' not in ''.join(latest_tail[-80:]):
                late_issues.append(line.rstrip())
        if 'ERROR -' in line and not any(tok in line for tok in ['shutdown-in-progress:wait_for_messages_stable']):
            late_issues.append(line.rstrip())

    need_fix = []
    if verify_mode_hits and not any('verify_mode=usable' in x or 'group-opened-usable-unverified' in x for x in verify_mode_hits):
        need_fix.append('chưa thấy evidence usable-mode trong log mới; cần soak thêm')
    if any('navigation-stall' in x for x in verify_mode_hits):
        need_fix.append('đã xuất hiện navigation-stall; cần soi artifact và recovery path')
    if any('group-opened-unverified' in x for x in hard_regressions):
        need_fix.append('lỗi group-opened-unverified đã quay lại')
    if any('HTTPConnectionPool(' in x or 'Read timed out' in x for x in hard_regressions):
        need_fix.append('timeout WebDriver/local transport đã quay lại')
    if not need_fix:
        need_fix.append('chưa thấy lỗi gốc lớn quay lại; tiếp tục soak và bổ sung test env')

    return {
        'running': process_running(),
        'latest_log': str(latest) if latest else None,
        'room_switch_ok': room_switch_ok,
        'fairness_ok': fairness_ok,
        'hard_regressions': hard_regressions[-20:],
        'verify_mode_hits': verify_mode_hits[-20:],
        'late_issues': late_issues[-20:],
        'need_fix': need_fix,
    }


if __name__ == '__main__':
    print(json.dumps(summarize(), ensure_ascii=False))
