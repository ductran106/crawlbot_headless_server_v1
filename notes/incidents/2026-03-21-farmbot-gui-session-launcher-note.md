# Farmbot GUI session launcher note — 2026-03-21

## Symptom
Portable Crawlbot on farmbot failed from SSH with:
- `session not created: Chrome instance exited`

## Exact root cause
Headed Chromium was launched from an SSH session that had no desktop GUI context.
Direct probe showed:
- `Missing X server or $DISPLAY`

## Verified fix / workaround
Launch the bot in the real `farm4bot` GNOME/Xwayland session with:
- `DISPLAY=:0`
- `XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth...`
- `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`

## Durable launcher
Portable repo on farmbot now has:
- `run-gui-session.sh`
- `README-RUN-GUI-SESSION.txt`

`run-gui-session.sh` auto-detects the Xwayland auth file and exports the required GUI-session env before running `./.venv/bin/python main.py`.

## Verification
`run-gui-session.sh` was tested successfully:
- Chromium/WebDriver startup passed
- Zalo Web opened
- login reached `qr-visible`
- QR screenshots were captured
- QR delivery to Telegram began normally

## Recognition rule for future incidents
If farmbot Crawlbot works from the desktop terminal but fails from SSH with Chrome startup errors, suspect missing GUI session env first, not browser installation or app logic.
