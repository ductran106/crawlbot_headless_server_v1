import json
import logging
from datetime import datetime

from .config import COMPUTER_NAME, get_session_id
from .logger import default_logger


def build_event_payload(event_name, *, now=None, group=None, host=None, session_id=None, **fields):
    """Tạo structured payload chuẩn cho observability events."""
    now = now or datetime.now()
    payload = {
        "event": event_name,
        "ts": now.isoformat(),
        "session_id": session_id or get_session_id(now),
        "host": host or COMPUTER_NAME,
    }
    if group is not None:
        payload["group"] = group
    payload.update(fields)
    return payload


def format_event_log(event_name, payload=None, prefix=None):
    """Chuẩn hóa structured event log thành một JSON-line ổn định."""
    data = dict(payload or {})
    data.setdefault("event", event_name)
    line_prefix = prefix or event_name.upper()
    return f"{line_prefix} {json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"


def log_event(event_name, payload=None, *, prefix=None, level=logging.INFO, logger=default_logger):
    """Ghi structured event log với prefix cố định + JSON compact."""
    logger.log(level, format_event_log(event_name, payload=payload, prefix=prefix))


def build_room_switch_tracker_snapshot(
    group_name,
    tracker,
    *,
    processed_count,
    backlog_pressure,
    possible_gap,
    stay_budget,
    next_idx,
    sleep_s,
    room_cycle,
    verify_mode=None,
    gap_risk_reason=None,
    navigation_possible_gap=None,
    crawler_possible_gap=None,
    revisit_boost_hint=None,
    retry_attempt=None,
    navigation_status_code=None,
    now=None,
):
    """Tạo snapshot observability cho từng vòng room-switch."""
    tracker = dict(tracker or {})
    payload = build_event_payload(
        "room_switch_tracker",
        now=now,
        group=group_name,
        room_cycle=max(1, int(room_cycle or 1)),
        processed_count=max(0, int(processed_count or 0)),
        backlog_pressure=bool(backlog_pressure),
        possible_gap=bool(possible_gap),
        pressure_streak=int(tracker.get("pressure_streak", 0) or 0),
        gap_streak=int(tracker.get("gap_streak", 0) or 0),
        backlog_hot=bool(tracker.get("backlog_hot", False)),
        stay_budget=max(1, int(stay_budget or 1)),
        next_group_index=max(0, int(next_idx or 0)),
        sleep_s=max(0, int(sleep_s or 0)),
        verify_mode=verify_mode,
        gap_risk_reason=gap_risk_reason,
        navigation_possible_gap=bool(navigation_possible_gap) if navigation_possible_gap is not None else None,
        crawler_possible_gap=bool(crawler_possible_gap) if crawler_possible_gap is not None else None,
        revisit_boost_hint=bool(revisit_boost_hint) if revisit_boost_hint is not None else None,
        retry_attempt=int(retry_attempt or 0) if retry_attempt is not None else None,
        navigation_status_code=navigation_status_code,
    )
    return payload


def build_browser_recovery_payload(event_name, *, groups=None, now=None, success=None, step=None, error=None, **fields):
    """Tạo payload chuẩn cho browser recovery ở scheduler/main loop."""
    payload = build_event_payload(
        event_name,
        now=now,
        groups=list(groups or []),
        **fields,
    )
    if success is not None:
        payload["success"] = bool(success)
    if step is not None:
        payload["step"] = step
    if error is not None:
        payload["error"] = str(error)
    return payload
