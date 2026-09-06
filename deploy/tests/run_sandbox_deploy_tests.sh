#!/usr/bin/env bash
#
# Dry-run harness proving deploy/sandbox-deploy.sh, with a fake `sbx` and a fake
# `systemctl` placed first on PATH (deploy/tests/fake-bin). It follows the same
# pattern as run_deploy_tests.sh, which proves deploy/deploy.sh against a fake
# `docker` and `curl`. No real sandbox tool, sandbox, daemon or service is
# touched: nothing is created, started, stopped or removed.
#
#   S1  creates the sandbox when `sbx ls` does not list it, with exactly the
#       name, memory, processor count and published ports the profile asked for
#   S2  does not create it when `sbx ls` already lists it
#   S3  adds the outbound network rules once — a second run with the rules
#       already listed adds nothing
#   S4  same, on a version of sbx that cannot list one sandbox's rules: the
#       first run writes the note, the second run reads it and adds nothing
#   S5  starts the keeper service for this sandbox
#   S6  runs deploy/deploy.sh inside with exactly the expected arguments, and
#       the mode signal set outside really reaches the inner run
#   S7  the steps happen in order: create, then rules, then keeper, then deploy
#   S8  passes the inner exit code through — 0 stays 0, 3 stays 3
#   S9  refuses loudly, and does nothing at all, when no sandbox is named
#
# Run: deploy/tests/run_sandbox_deploy_tests.sh   (exit 0 = all pass)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../.." && pwd)"
WRAPPER="${REPO_ROOT}/deploy/sandbox-deploy.sh"
FAKE_BIN="${HERE}/fake-bin"

# The note the wrapper keeps when sbx cannot list one sandbox's rules. The tests
# own it: each case starts without it unless the case put it there itself.
MARKER_FILE="${REPO_ROOT}/.guardkit/tmp/sandbox-network-rules-api-test-deploy"

# The profile's settings, threaded in exactly as the deploy stage will thread
# them (comma-joined lists, no YAML parsing anywhere in the wrapper).
S_NAME="api-test-deploy"
S_MEMORY="6g"
S_CPUS="4"
S_PUBLISH="127.0.0.1:8901:8901,127.0.0.1:8902:8902"
S_ALLOW="deb.debian.org,security.debian.org,*.debian.org,pypi.org,files.pythonhosted.org"

PASS=0
FAIL=0

# Runs the wrapper in an isolated scratch dir with fresh logs, then echoes what
# it did and leaves the logs in LAST_* for the caller's assertions. Any extra
# environment (the mode signal, the fake's answers) is set by the caller.
run_case() {
  local name="$1"
  local scratch
  scratch="$(mktemp -d)"
  export FAKE_SBX_LOG="${scratch}/sbx.log"
  export FAKE_SYSTEMCTL_LOG="${scratch}/systemctl.log"
  : >"${FAKE_SBX_LOG}"
  : >"${FAKE_SYSTEMCTL_LOG}"

  local out rc
  set +e
  out="$(PATH="${FAKE_BIN}:${PATH}" "${WRAPPER}" 2>&1)"
  rc=$?
  set -e

  echo "----- ${name} (exit ${rc}) -----"
  echo "${out}"
  echo "--- sbx.log ---"
  cat "${FAKE_SBX_LOG}"
  echo "--- systemctl.log ---"
  cat "${FAKE_SYSTEMCTL_LOG}"
  echo

  LAST_OUT="${out}"
  LAST_RC="${rc}"
  LAST_SBX_LOG="$(cat "${FAKE_SBX_LOG}")"
  LAST_SYSTEMCTL_LOG="$(cat "${FAKE_SYSTEMCTL_LOG}")"
  rm -rf "${scratch}"
}

assert() {
  local desc="$1"
  shift
  if "$@"; then
    echo "  PASS: ${desc}"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: ${desc}"
    FAIL=$((FAIL + 1))
  fi
}

has() { printf '%s' "$2" | grep -qF -- "$1"; }
lacks() { ! printf '%s' "$2" | grep -qF -- "$1"; }
# has_line "<exact line>" "$log": the log contains this line and nothing more on
# it -- this is how the argument lists are pinned exactly, not loosely matched.
has_line() { printf '%s\n' "$2" | grep -qxF -- "$1"; }
# before "A" "B" "$log": the first line matching A comes before the first
# matching B (both must be present).
before() {
  local a b hay al bl
  a="$1"; b="$2"; hay="$3"
  al="$(printf '%s\n' "${hay}" | grep -nF -- "${a}" | head -n1 | cut -d: -f1)"
  bl="$(printf '%s\n' "${hay}" | grep -nF -- "${b}" | head -n1 | cut -d: -f1)"
  [[ -n "${al}" && -n "${bl}" && "${al}" -lt "${bl}" ]]
}

# The exact argument lists the wrapper must produce.
EXPECT_CREATE="sbx create shell ${REPO_ROOT} --name ${S_NAME} --memory ${S_MEMORY} --cpus ${S_CPUS} --publish 127.0.0.1:8901:8901 --publish 127.0.0.1:8902:8902"
EXPECT_ALLOW="sbx policy allow network --sandbox ${S_NAME} ${S_ALLOW}"
EXPECT_EXEC="sbx exec -w ${REPO_ROOT} -e CANDIDATE -e PROMOTE -e REVERT -e CANDIDATE_DOWN -e CANDIDATE_PORT -e ROLLBACK_IMAGE_REF -e ENV_FILE ${S_NAME} deploy/deploy.sh"
EXPECT_KEEPER="systemctl --user start forge-sandbox-keeper@${S_NAME}"

# Every case starts from a clean slate for the note file.
rm -f "${MARKER_FILE}"

# --- S1: the sandbox is absent -> create it, exactly as the profile asks ------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="" FAKE_SBX_POLICY_LS_RC=0 FAKE_SBX_POLICY_LS="" \
  run_case "S1 sandbox absent -> created"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "asked sbx what already exists" has_line "sbx ls" "${LAST_SBX_LOG}"
assert "created the sandbox with exactly the profile's settings" \
  has_line "${EXPECT_CREATE}" "${LAST_SBX_LOG}"
assert "published BOTH ports back to the host loopback" \
  has "--publish 127.0.0.1:8901:8901 --publish 127.0.0.1:8902:8902" "${LAST_SBX_LOG}"
rm -f "${MARKER_FILE}"

# --- S2: the sandbox is already there -> do not create it --------------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="NAME            STATUS
${S_NAME}   running" \
  FAKE_SBX_POLICY_LS_RC=0 FAKE_SBX_POLICY_LS="${S_ALLOW}" \
  run_case "S2 sandbox present -> not created"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "did NOT create a second sandbox" lacks "sbx create" "${LAST_SBX_LOG}"
assert "said plainly that it was already there" \
  has "sandbox ${S_NAME} already exists" "${LAST_OUT}"
assert "still ran the deploy inside" has_line "${EXPECT_EXEC}" "${LAST_SBX_LOG}"
rm -f "${MARKER_FILE}"

# --- S2b: a similar name is not the same sandbox -----------------------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="NAME            STATUS
${S_NAME}-2   running" \
  FAKE_SBX_POLICY_LS_RC=0 FAKE_SBX_POLICY_LS="" \
  run_case "S2b only a similarly-named sandbox exists -> still created"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "created its own sandbox, not reusing the similarly-named one" \
  has_line "${EXPECT_CREATE}" "${LAST_SBX_LOG}"
rm -f "${MARKER_FILE}"

# --- S3: the network rules go on once, when sbx CAN list them ----------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="" FAKE_SBX_POLICY_LS_RC=0 FAKE_SBX_POLICY_LS="" \
  run_case "S3a rules absent -> added once"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "added the rules with exactly the profile's list, comma-joined" \
  has_line "${EXPECT_ALLOW}" "${LAST_SBX_LOG}"
assert "added them exactly once" \
  test "$(printf '%s\n' "${LAST_SBX_LOG}" | grep -cF -- 'sbx policy allow network')" -eq 1
rm -f "${MARKER_FILE}"

SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_POLICY_LS_RC=0 \
  FAKE_SBX_POLICY_LS="deb.debian.org
security.debian.org
*.debian.org
pypi.org
files.pythonhosted.org" \
  run_case "S3b rules already listed -> not added again"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "did NOT add the rules a second time" \
  lacks "sbx policy allow network" "${LAST_SBX_LOG}"
assert "said plainly that the rules were already there" \
  has "outbound network rules already in place" "${LAST_OUT}"
rm -f "${MARKER_FILE}"

# One rule missing from the list is not "already in place".
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_POLICY_LS_RC=0 \
  FAKE_SBX_POLICY_LS="deb.debian.org
security.debian.org
*.debian.org
pypi.org" \
  run_case "S3c one rule missing -> the rules are applied"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "applied the full rule list again" has_line "${EXPECT_ALLOW}" "${LAST_SBX_LOG}"
rm -f "${MARKER_FILE}"

# --- S4: same, on an sbx that cannot list one sandbox's rules ----------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="" FAKE_SBX_POLICY_LS_RC=2 \
  run_case "S4a sbx cannot list rules, no note yet -> added once"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "added the rules" has_line "${EXPECT_ALLOW}" "${LAST_SBX_LOG}"
assert "wrote the note recording what it applied" test -f "${MARKER_FILE}"
assert "the note holds the exact rule list" \
  has_line "${S_ALLOW}" "$(cat "${MARKER_FILE}")"

# Second run, note in place -> nothing added.
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_POLICY_LS_RC=2 \
  run_case "S4b sbx cannot list rules, note in place -> not added again"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "did NOT add the rules a second time" \
  lacks "sbx policy allow network" "${LAST_SBX_LOG}"

# A changed rule list is a different note -> applied again.
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW},172.30.1.253:4000" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_POLICY_LS_RC=2 \
  run_case "S4c the rule list changed -> applied again"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "applied the new rule list" \
  has_line "sbx policy allow network --sandbox ${S_NAME} ${S_ALLOW},172.30.1.253:4000" "${LAST_SBX_LOG}"
rm -f "${MARKER_FILE}"

# --- S5: the keeper is started ----------------------------------------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="" FAKE_SBX_POLICY_LS_RC=0 FAKE_SBX_POLICY_LS="" \
  run_case "S5 the keeper is started for this sandbox"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "started the keeper as a user service, named for this sandbox" \
  has_line "${EXPECT_KEEPER}" "${LAST_SYSTEMCTL_LOG}"
assert "started nothing else" \
  test "$(printf '%s\n' "${LAST_SYSTEMCTL_LOG}" | grep -c 'systemctl')" -eq 1
assert "never stopped or disabled anything" lacks "stop" "${LAST_SYSTEMCTL_LOG}"
rm -f "${MARKER_FILE}"

# --- S6: the inner run, exact arguments and a real mode signal ---------------
CANDIDATE=1 CANDIDATE_PORT=8902 ROLLBACK_IMAGE_REF="apitest-app:rollback-pre-deploy" \
  SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_POLICY_LS_RC=0 FAKE_SBX_POLICY_LS="${S_ALLOW}" \
  run_case "S6 runs deploy.sh inside with exactly the expected arguments"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "exact arguments: working directory, the seven passed-through names, sandbox, script" \
  has_line "${EXPECT_EXEC}" "${LAST_SBX_LOG}"
for _n in CANDIDATE PROMOTE REVERT CANDIDATE_DOWN CANDIDATE_PORT ROLLBACK_IMAGE_REF ENV_FILE; do
  assert "passes ${_n} through to the inner run" \
    has "sbx-exec-env ${_n}=" "${LAST_SBX_LOG}"
done
assert "the candidate mode signal really reaches the inner run" \
  has_line "sbx-exec-env CANDIDATE=1" "${LAST_SBX_LOG}"
assert "the candidate port really reaches the inner run" \
  has_line "sbx-exec-env CANDIDATE_PORT=8902" "${LAST_SBX_LOG}"
assert "the rollback tag really reaches the inner run" \
  has_line "sbx-exec-env ROLLBACK_IMAGE_REF=apitest-app:rollback-pre-deploy" "${LAST_SBX_LOG}"
assert "runs the repository's own deploy script, unchanged" \
  has "${S_NAME} deploy/deploy.sh" "${LAST_SBX_LOG}"
assert "does not pass any name beyond the seven agreed" \
  test "$(printf '%s\n' "${LAST_SBX_LOG}" | grep -c '^sbx-exec-env ')" -eq 7
rm -f "${MARKER_FILE}"

# --- S7: the order of the steps ---------------------------------------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="" FAKE_SBX_POLICY_LS_RC=0 FAKE_SBX_POLICY_LS="" \
  run_case "S7 create, then rules, then keeper, then deploy"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "creates before it adds the rules" \
  before "sbx create" "sbx policy allow network" "${LAST_SBX_LOG}"
assert "adds the rules before it runs the deploy" \
  before "sbx policy allow network" "sbx exec" "${LAST_SBX_LOG}"
assert "starts the keeper before it runs the deploy" \
  before "starting the keeper" "running deploy/deploy.sh inside" "${LAST_OUT}"
rm -f "${MARKER_FILE}"

# --- S8: the inner exit code is passed through, verbatim ---------------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_POLICY_LS_RC=0 FAKE_SBX_POLICY_LS="${S_ALLOW}" \
  FAKE_SBX_EXEC_RC=0 \
  run_case "S8a the inner deploy succeeds -> exit 0"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "reported the inner exit code" has "exited 0" "${LAST_OUT}"
rm -f "${MARKER_FILE}"

SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_POLICY_LS_RC=0 FAKE_SBX_POLICY_LS="${S_ALLOW}" \
  FAKE_SBX_EXEC_RC=3 \
  run_case "S8b the inner deploy fails with 3 -> exit 3, not 1"
assert "exit 3, the inner code exactly" test "${LAST_RC}" -eq 3
assert "reported the inner exit code" has "exited 3" "${LAST_OUT}"
rm -f "${MARKER_FILE}"

# --- S9: no sandbox named -> refuse loudly, do nothing -----------------------
SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="" \
  run_case "S9 no sandbox named -> refuses, touches nothing"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "says plainly what is missing and that it is refusing" \
  has "FATAL: SANDBOX_NAME is not set" "${LAST_OUT}"
assert "ran no sbx at all" lacks "sbx" "${LAST_SBX_LOG}"
assert "started no service at all" lacks "systemctl" "${LAST_SYSTEMCTL_LOG}"
rm -f "${MARKER_FILE}"

# --- S10: the profile and the wrapper agree (static) -------------------------
_PROFILE="$(cat "${REPO_ROOT}/deploy/profile.yaml")"
assert "the profile runs the sandbox wrapper for the compose step" \
  has "script: deploy/sandbox-deploy.sh" "${_PROFILE}"
assert "the profile names the sandbox" has "name: api-test-deploy" "${_PROFILE}"
assert "the profile asks for 6g of memory" has "memory: 6g" "${_PROFILE}"
assert "the profile asks for 4 processors" has "cpus: 4" "${_PROFILE}"
assert "the profile publishes both ports to the host loopback" \
  has 'publish: ["127.0.0.1:8901:8901", "127.0.0.1:8902:8902"]' "${_PROFILE}"
assert "the profile carries the five outbound rules" \
  has 'allow_network: ["deb.debian.org", "security.debian.org", "*.debian.org", "pypi.org", "files.pythonhosted.org"]' "${_PROFILE}"
assert "the repository's own deploy script is still there, unchanged in role" \
  test -x "${REPO_ROOT}/deploy/deploy.sh"

# --- tidy up -----------------------------------------------------------------
# Leave nothing behind: the note the wrapper may write is build-time state, and
# these tests own the one they caused.
rm -f "${MARKER_FILE}"
rmdir "${REPO_ROOT}/.guardkit/tmp" 2>/dev/null || true

# --- summary -----------------------------------------------------------------
echo "================================"
echo "PASS=${PASS} FAIL=${FAIL}"
if [[ "${FAIL}" -ne 0 ]]; then
  exit 1
fi
echo "ALL SANDBOX-DEPLOY TESTS PASSED"
