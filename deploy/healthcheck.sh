#!/usr/bin/env bash
#
# api_test vetted health-check script (the forge health_check step runs THIS,
# not a freehand shell line — the FMDR D12 law: vetted scripts only, exit code
# is the health verdict). C4 live-caught (2026-07-16): the profile previously
# put a `curl -fsS ...` COMMAND LINE in health_checks.cmd; the no-shell
# executor treats the whole string as one filename -> exit 127.
#
# Healthy = GET /health answers 200 AND reports the database connected.
set -euo pipefail

HEALTH_URL="${HEALTH_URL:-http://localhost:8901/health}"
HEALTH_EXPECT="${HEALTH_EXPECT:-\"database\":\"connected\"}"

body="$(curl -fsS "${HEALTH_URL}")"
if printf '%s' "${body}" | grep -qF -- "${HEALTH_EXPECT}"; then
  printf '[healthcheck.sh] healthy: %s\n' "${body}"
  exit 0
fi
printf '[healthcheck.sh] UNHEALTHY: %s did not contain %s; body: %s\n' "${HEALTH_URL}" "${HEALTH_EXPECT}" "${body}" >&2
exit 1
