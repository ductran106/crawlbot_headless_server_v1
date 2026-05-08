# Evidence Report — Observed 1-Day Run (3-room) — v1 Lock

Repo: `/home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab`
Run ID: `observed-1day-3room-20260323-201856`
Run log: `runs/observed-1day-3room-20260323-201856/runtime.log`
Review date: 2026-03-24

## Executive summary

### Verdict
- **Scheduler fairness 3-room: PASS mạnh**
- **Runtime recovery: PASS có điều kiện**
- **Browser stability dài hạn: CHƯA PASS tuyệt đối**
- **Overall verdict:** khóa mốc hiện tại thành **v1 usable stable baseline**, chưa gọi là production-grade tuyệt đối.

### What this run proved
- 3-room fairness rất đều:
  - `RETURN ROOM LỊCH`: 2101 tracker events
  - `RET 2 ROOM LỊCH`: 2101 tracker events
  - `HEY KLUB`: 2100 tracker events
- `max_consecutive = 1` cho cả 3 room.
- `selected_by` gần như hoàn toàn là `starvation_guard` (6300/6302).
- Room 3 (`HEY KLUB`) không còn bị bỏ quên.
- End-of-run finalize sạch: save final docx, format docx, Telegram text notify, Telegram document send, browser shutdown.

### Why not production-grade absolute yet
Observed run 1 ngày vẫn có **10 incident clusters** với pattern `Message: tab crashed`, rải đều qua nhiều time windows. Recovery đứng dậy được, nhưng crash-rate hiện tại vẫn đủ cao để chưa chốt browser/runtime là “ổn định tuyệt đối”.

---

## Incident summary

### Aggregate counts
- `ROOM_SWITCH_TRACKER`: 6302
- `ERROR`: 68
- `WARNING`: 716
- `Traceback`: 0
- restart-related hits: 40
- recover-related hits: 20
- `SAVE_DOCUMENT_RESULT success=true`: 21
- Telegram document send success: 21
- Telegram notify success: 351

### Crash clusters observed
1. `2026-03-23 22:39` — crash while processing messages in `RETURN ROOM LỊCH`
2. `2026-03-24 01:09` — crash during verify/open `RET 2 ROOM LỊCH`
3. `2026-03-24 03:51` — `group-opened-unverified` around `HEY KLUB`, then crash while moving back to `RETURN ROOM LỊCH`
4. `2026-03-24 06:29` — crash shortly after opening `HEY KLUB`
5. `2026-03-24 08:41` — crash while scrolling in `HEY KLUB`
6. `2026-03-24 10:54` — crash during room search after processing alerts in `RETURN ROOM LỊCH`
7. `2026-03-24 13:03` — `group-opened-unverified` then crash during search/open flow
8. `2026-03-24 15:07` — `group-opened-unverified` + fail-artifact capture failure, then crash
9. `2026-03-24 17:14` — direct crash in `crawl_step` while inside `HEY KLUB`
10. `2026-03-24 19:21` — crash while processing messages in `RETURN ROOM LỊCH`

### Recovery assessment
Recovery path worked repeatedly:
- detect tab/browser failure
- restart WebDriver
- reopen Zalo surface
- reopen target group
- continue crawl

No Python-level fatal traceback was observed. Run completed and finalized artifacts successfully.

---

## Fairness review

### Tracker evidence
- `RETURN ROOM LỊCH`: 2101
- `RET 2 ROOM LỊCH`: 2101
- `HEY KLUB`: 2100
- `bootstrap_never_visited`: 2
- `starvation_guard`: 6300
- `max_consecutive`: 1 for all rooms
- `max_starvation_seconds`: 0.0
- `possible_gap_true`: 0
- `backlog_pressure_true`: 93
- `backlog_hot_true`: 8

### Fairness conclusion
Scheduler fairness-first behavior is now strong enough to treat as **proven for the 3-room observed lane**. No meaningful sticky-room pattern reappeared. No room starvation was observed.

---

## Room 3 / HEY KLUB review

### Evidence
- HEY KLUB appeared in tracker 2100 times.
- HEY KLUB was opened successfully in real navigation multiple times.
- HEY KLUB produced real message crawls.
- HEY KLUB final docx save + formatting + Telegram send succeeded at run end.

### Caveat
HEY KLUB still appears in several crash-adjacent windows (`verify`, `scroll`, `crawl_step`). So room 3 is **no longer a fairness problem**, but remains a good surface for exposing browser/runtime fragility.

---

## Runtime quality review

### Good signs
- fairness across 3 rooms is excellent
- recovery succeeds repeatedly
- finalize pipeline is clean
- no full-process death / no incomplete run termination

### Bad signs
- 10 crash clusters in ~24h is still too many for “absolute production-grade”
- crash occurs across multiple UI phases, not one isolated callsite
- `group-opened-unverified` still appears
- fail-artifact screenshot/sidecar capture is not yet reliable because fail-artifact paths are not always writable/present

### Overall runtime interpretation
The main bottleneck is **browser/runtime long-run stability**, not scheduler logic.

---

## Decision after review

### Lock decision
Lock the current state as:
- **`scheduler/runtime v1`**
- meaning: **usable stable baseline** with fairness proven and recovery proven, but not yet browser-perfect.

### Patch direction after v1 lock
Recommended next patch order:
1. `src/browser/driver.py`
   - proactive browser/session health policy
   - reduce tab-crash frequency
   - consider scheduled soft recycle or better health-triggered recycle
2. `src/browser/navigation.py`
   - harden `group-opened-unverified` verification path
   - reduce false-negative room verification
3. fail-artifact hygiene
   - ensure `data/logs/fail-artifacts/` exists and capture is reliable
4. do **not** open `message_crawler.py` first unless new evidence specifically points there

---

## One-line conclusion

> After the 1-day observed 3-room run, the correct lock is: **v1 stable operational baseline achieved; scheduler fairness is effectively proven, but browser/runtime still needs hardening before claiming absolute production-grade status.**
