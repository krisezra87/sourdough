#!/usr/bin/env bash
# Install (or re-install) watch mode's timer on this machine.
# Usage: tools/install-watch.sh            install and start
#        tools/install-watch.sh --uninstall
#
# Safe to re-run, e.g. after moving the repo or setting up a new computer. It
#   1. checks the dependencies (python3 + numpy + Pillow, rsync, ssh alias "ha")
#   2. writes tools/watch_secret (gitignored): the HA webhook URL, built from the
#      webhook id in the "Starter watch - notify" automation in automations.yaml
#   3. writes ~/.config/systemd/user/starter-watch.{service,timer} pointing at this
#      checkout, and enables the timer
# The timer runs watch_service.py at :02 and :32 past each hour (just after each
# 30 minute frame); the script exits straight away if watch mode is off.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HA_REPO="${HA_REPO:-$HOME/GIT/ha-repo}"   # the Home Assistant repo (automations.yaml holds the webhook id)
UNIT_DIR="$HOME/.config/systemd/user"
HA_URL="${HA_URL:-http://192.168.1.50:8123}"

if [[ "${1:-}" == "--uninstall" ]]; then
  systemctl --user disable --now starter-watch.timer 2>/dev/null || true
  rm -f "$UNIT_DIR/starter-watch.service" "$UNIT_DIR/starter-watch.timer"
  systemctl --user daemon-reload
  echo "removed starter-watch timer (tools/watch_secret and ~/.cache/starter-watch left alone)"
  exit 0
fi

fail() { echo "error: $*" >&2; exit 1; }

command -v python3 >/dev/null || fail "python3 not found"
python3 -c "import numpy, PIL" 2>/dev/null || fail "python3 needs numpy and Pillow (e.g. pacman -S python-numpy python-pillow)"
command -v rsync >/dev/null || fail "rsync not found"
ssh -o ConnectTimeout=8 -o BatchMode=yes ha true 2>/dev/null \
  || fail "cannot ssh to host alias 'ha' (see the same alias used by tools/sync.sh in ~/.ssh/config)"

WID="$(python3 - "$HA_REPO/automations.yaml" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
block = text[text.index("alias: Starter watch - notify"):]
print(re.search(r"webhook_id:\s*(\S+)", block).group(1))
PY
)"
printf '%s/api/webhook/%s\n' "$HA_URL" "$WID" > "$HERE/watch_secret"
chmod 600 "$HERE/watch_secret"

mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/starter-watch.service" <<UNIT
[Unit]
Description=Check whether the sourdough starter has peaked (watch mode)

[Service]
Type=oneshot
ExecStart=/usr/bin/env python3 $HERE/watch_service.py
UNIT
cat > "$UNIT_DIR/starter-watch.timer" <<UNIT
[Unit]
Description=Run the starter watch check just after each timelapse frame

[Timer]
OnCalendar=*:02,32
Persistent=false

[Install]
WantedBy=timers.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now starter-watch.timer
echo "installed. next runs:"
systemctl --user list-timers starter-watch.timer --no-pager | head -3
echo "test the whole chain with: $HERE/watch_service.py --dry-run"
