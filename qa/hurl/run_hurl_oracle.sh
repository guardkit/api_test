#!/usr/bin/env bash
# HTTP-kind oracle: run the Hurl worked-examples over the wire and map Hurl's
# exit tri-state onto the behavioural_oracle contract (exit 0 pass / 1 fail).
# This is the command behind behavioural_oracle.command — no Python test file.
#
#   APP_BASE_URL=http://host:port MARKER=<run-id> qa/hurl/run_hurl_oracle.sh
#
# The seed "Given" that is NOT an HTTP step would live HERE (e.g. psql exec)
# before the hurl run. For /users the marker is created through the product API
# inside the .hurl itself, so no pre-seed is needed.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
HURL_BIN="${HURL_BIN:-$HOME/.local/bin/hurl}"
BASE="${APP_BASE_URL:?APP_BASE_URL required}"
MARKER="${MARKER:-$(date +%s)-$$}"
# Fresh receipts dir per run (Hurl reports APPEND — the dossier fence).
REPORT_DIR="$(mktemp -d -t hurl-oracle-XXXXXX)"

set +e
"$HURL_BIN" --variable "host=${BASE}" --variable "marker=${MARKER}" \
  --report-json "$REPORT_DIR" --error-format long \
  "$HERE/users_roundtrip.hurl"
code=$?
set -e

echo "hurl_exit=$code report_dir=$REPORT_DIR" >&2
case "$code" in
  0) echo "PASS: over-the-wire round-trip green (marker=$MARKER)"; exit 0 ;;
  4) echo "FAIL: app failed the spec (assert/status mismatch)"; exit 1 ;;
  3) echo "FAIL: could not connect — sandbox/app down"; exit 1 ;;
  2) echo "FAIL: malformed .hurl (generator bug, not an app defect)"; exit 1 ;;
  *) echo "FAIL: hurl exit $code"; exit 1 ;;
esac
