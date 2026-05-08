#!/usr/bin/env python3
import json
import os
import sys
from collections import Counter, defaultdict
from glob import glob


def extract_payload(line: str):
    marker = "ROOM_SWITCH_TRACKER "
    if marker not in line:
        return None
    try:
        payload = line.split(marker, 1)[1].strip()
        return json.loads(payload)
    except Exception:
        return None


def iter_log_files(path_arg: str | None):
    if path_arg:
        if os.path.isdir(path_arg):
            for p in sorted(glob(os.path.join(path_arg, "**", "*"), recursive=True)):
                if os.path.isfile(p):
                    yield p
        elif os.path.isfile(path_arg):
            yield path_arg
        return

    for p in sorted(glob("logs/**/*", recursive=True)):
        if os.path.isfile(p):
            yield p


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    total_events = 0
    per_group = defaultdict(lambda: {
        "events": 0,
        "max_starvation": 0.0,
        "max_consecutive": 0,
        "max_sleep": 0,
        "processed_sum": 0,
        "backlog_pressure_count": 0,
        "possible_gap_count": 0,
        "backlog_hot_count": 0,
        "selected_by": Counter(),
    })

    for log_file in iter_log_files(target):
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    payload = extract_payload(line)
                    if not payload:
                        continue
                    total_events += 1
                    group = payload.get("group", "UNKNOWN")
                    state = per_group[group]
                    state["events"] += 1
                    state["processed_sum"] += int(payload.get("processed_count", 0) or 0)
                    state["max_starvation"] = max(state["max_starvation"], float(payload.get("starvation_seconds", 0) or 0))
                    state["max_consecutive"] = max(state["max_consecutive"], int(payload.get("consecutive_visits", 0) or 0))
                    state["max_sleep"] = max(state["max_sleep"], int(payload.get("sleep_s", 0) or 0))
                    if payload.get("backlog_pressure"):
                        state["backlog_pressure_count"] += 1
                    if payload.get("possible_gap"):
                        state["possible_gap_count"] += 1
                    if payload.get("backlog_hot"):
                        state["backlog_hot_count"] += 1
                    if payload.get("selected_by"):
                        state["selected_by"][payload["selected_by"]] += 1
        except Exception as e:
            print(f"WARN: skip {log_file}: {e}", file=sys.stderr)

    if total_events == 0:
        print("No ROOM_SWITCH_TRACKER events found.")
        return 1

    print(f"ROOM_SWITCH_TRACKER summary :: total_events={total_events}")
    print()
    for group in sorted(per_group):
        state = per_group[group]
        avg_processed = state["processed_sum"] / max(1, state["events"])
        selected_by = ", ".join(f"{k}:{v}" for k, v in state["selected_by"].most_common()) or "n/a"
        print(f"[GROUP] {group}")
        print(f"  events                : {state['events']}")
        print(f"  avg_processed         : {avg_processed:.2f}")
        print(f"  max_starvation_sec    : {state['max_starvation']:.2f}")
        print(f"  max_consecutive       : {state['max_consecutive']}")
        print(f"  max_sleep_sec         : {state['max_sleep']}")
        print(f"  backlog_pressure_cnt  : {state['backlog_pressure_count']}")
        print(f"  possible_gap_cnt      : {state['possible_gap_count']}")
        print(f"  backlog_hot_cnt       : {state['backlog_hot_count']}")
        print(f"  selected_by           : {selected_by}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
