# HANDOFF_CRAWLBOT_HARDENING_2026-06-06

Date: 2026-06-06
Host: hanauda
Service: crawlbot-headless-hanauda.service
Status: CLOSED / production-frozen

## Completed work summary
Accepted and verified hardening changes:
- `.env` permission hardening to `600`
- DOCX content preservation fix (removed destructive `replace("-", "*")` / `replace("+", "*")` behavior)
- SQLite context-manager hardening (`with sqlite3.connect(...) as conn:`)
- Stale data archive for unused `return_room_lich` and `ret2_room_lich`
- systemd memory controls enabled
- Git baseline + hardening commits recorded

## Commit SHAs
- `a4113fa` — baseline: pre-hardening state (pre-phase-1)
- `4ba954e` — hardening phases 1-3: env security, docx content preservation, sqlite context managers

## Current systemd memory settings
Current unit settings for `crawlbot-headless-hanauda.service`:
- `MemoryAccounting=yes`
- `MemoryHigh=5G`
- `MemoryMax=6G`

## Rollback locations
- systemd unit live file:
  - `/etc/systemd/system/crawlbot-headless-hanauda.service`
- pre-memory-hardening unit backup:
  - `/etc/systemd/system/crawlbot-headless-hanauda.service.bak.20260605-110055`
- enabled symlink:
  - `/etc/systemd/system/multi-user.target.wants/crawlbot-headless-hanauda.service`
- git baseline for code comparison:
  - `a4113fa`

## Verified production state
Observation / validation results accepted for lane closure:
- `NRestarts = 0` during 24h observation window
- `OOM = 0`
- `OOMKill = 0`
- Service PID remained stable through observation
- Zalo session survives restart
- No QR login required after restart
- Crawl functioning normally
- Telegram functioning normally
- No restart loop observed
- No abnormal memory growth confirmed

## Known non-actionable observations
These were observed but are not actionable at closure time:
- Chrome profile storage is dominated by Zalo Web state under `chrome_user_data/Default/IndexedDB/https_chat.zalo.me_0.indexeddb.leveldb`
- Browser cache and code cache consume noticeable space, but no active disk-growth incident is open
- A few small bare `except:` blocks remain in runtime code, but there is no current production symptom justifying further change
- No further IndexedDB forensics, storage optimization, selector refactors, bare-except cleanup, architecture review, or performance tuning are approved in this closed lane

## Closure status
This hardening lane is CLOSED.

From this point forward, treat `crawlbot-headless-hanauda` as production-frozen unless explicitly reopened for a concrete production symptom such as:
- crawl failure
- message loss
- login loop
- QR re-authentication
- restart loop
- OOM
- abnormal memory growth
- disk growth incident
- Telegram failure

No further investigation should continue under this lane without explicit reopen approval.
