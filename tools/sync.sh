#!/usr/bin/env bash
# Pull the sourdough timelapse stills for one run from the HA machine.
# Usage: tools/sync.sh <run-name>      e.g. tools/sync.sh run0_bonne_maman
# The run name is whatever input_text.starter_run held while the shots were
# taken; photos land in photos/<run-name>/ (gitignored).
# Override HA_SSH / HA_DIR in the environment if your setup differs.
set -euo pipefail

HA_SSH="${HA_SSH:-ha}"
HA_DIR="${HA_DIR:-/media/starter}"

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <run-name>" >&2
  echo "run folders on $HA_SSH:$HA_DIR:" >&2
  ssh "$HA_SSH" "ls -d $HA_DIR/*/" >&2 || true
  exit 1
fi

RUN="$1"
DEST="$(dirname "$0")/../photos/$RUN/"
mkdir -p "$DEST"
rsync -av --include='2*.jpg' --exclude='*' "$HA_SSH:$HA_DIR/$RUN/" "$DEST"
