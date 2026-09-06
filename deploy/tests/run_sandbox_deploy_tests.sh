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
#   S3  asks the sandbox tool about each address in the profile's list, one at a
#       time, in the form the tool judges correctly: a bare host name asked
#       about as "http://<host>", an entry that already names a port asked about
#       exactly as written
#   S4  when every address is already allowed, adds nothing at all; when even
#       one is not, adds the whole list once, in a single call
#   S5  starts the keeper service for this sandbox
#   S6  runs deploy/deploy.sh inside with exactly the expected arguments, and
#       the mode signal set outside really reaches the inner run
#   S7  the steps happen in order: create, then ask about the addresses, then
#       the keeper, then the deploy
#   S8  passes the inner exit code through — 0 stays 0, 3 stays 3
#   S9  refuses loudly, and does nothing at all, when no sandbox is named
#   S10 writes no file anywhere under .guardkit/, and keeps no note of its own
#   S11 the profile and the wrapper agree, and the wrapper names no repository
#
# Run: deploy/tests/run_sandbox_deploy_tests.sh   (exit 0 = all pass)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../.." && pwd)"
WRAPPER="${REPO_ROOT}/deploy/sandbox-deploy.sh"
FAKE_BIN="${HERE}/fake-bin"

# The profile's settings, threaded in exactly as the deploy stage will thread
# them (comma-joined lists, no YAML parsing anywhere in the wrapper).
S_NAME="api-test-deploy"
S_MEMORY="6g"
S_CPUS="4"
S_PUBLISH="127.0.0.1:8901:8901,127.0.0.1:8902:8902"
S_ALLOW="deb.debian.org,security.debian.org,*.debian.org,pypi.org,files.pythonhosted.org"
# The same five as the wrapper asks about them: bare host names are asked about
# over plain HTTP, because the sandbox tool judges a bare host name as if it
# were port 443 and the Debian mirrors are fetched over plain HTTP.
S_ALLOW_ASKED="http://deb.debian.org,http://security.debian.org,http://*.debian.org,http://pypi.org,http://files.pythonhosted.org"

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
# count "<fixed text>" "$log": how many lines of the log contain it.
count() { printf '%s\n' "$2" | grep -cF -- "$1" || true; }
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
# One "is this address allowed?" question per entry of the profile's list. A
# bare host is asked about over plain HTTP, because the sandbox tool judges a
# bare host name as if it were port 443 and the Debian mirrors are plain HTTP.
CHECK_PREFIX="sbx policy check network --sandbox ${S_NAME}"

# --- S1: the sandbox is absent -> create it, exactly as the profile asks ------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="" FAKE_SBX_DENIED="" \
  run_case "S1 sandbox absent -> created"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "asked sbx what already exists" has_line "sbx ls" "${LAST_SBX_LOG}"
assert "created the sandbox with exactly the profile's settings" \
  has_line "${EXPECT_CREATE}" "${LAST_SBX_LOG}"
assert "published BOTH ports back to the host loopback" \
  has "--publish 127.0.0.1:8901:8901 --publish 127.0.0.1:8902:8902" "${LAST_SBX_LOG}"

# --- S2: the sandbox is already there -> do not create it --------------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="NAME            STATUS
${S_NAME}   running" \
  FAKE_SBX_DENIED="" \
  run_case "S2 sandbox present -> not created"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "did NOT create a second sandbox" lacks "sbx create" "${LAST_SBX_LOG}"
assert "said plainly that it was already there" \
  has "sandbox ${S_NAME} already exists" "${LAST_OUT}"
assert "still ran the deploy inside" has_line "${EXPECT_EXEC}" "${LAST_SBX_LOG}"

# --- S2b: a similar name is not the same sandbox -----------------------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="NAME            STATUS
${S_NAME}-2   running" \
  FAKE_SBX_DENIED="" \
  run_case "S2b only a similarly-named sandbox exists -> still created"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "created its own sandbox, not reusing the similarly-named one" \
  has_line "${EXPECT_CREATE}" "${LAST_SBX_LOG}"

# --- S3: the addresses are asked about one at a time, in the right form ------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" \
  SANDBOX_ALLOW_NETWORK="${S_ALLOW},172.30.1.253:4000" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_DENIED="" \
  run_case "S3 each address is asked about, bare hosts over plain HTTP"
assert "exit 0" test "${LAST_RC}" -eq 0
for _h in deb.debian.org security.debian.org '*.debian.org' pypi.org files.pythonhosted.org; do
  assert "asked whether ${_h} is allowed, as a plain-HTTP address" \
    has_line "${CHECK_PREFIX} http://${_h}" "${LAST_SBX_LOG}"
done
assert "asked about the address that already names a port exactly as written" \
  has_line "${CHECK_PREFIX} 172.30.1.253:4000" "${LAST_SBX_LOG}"
assert "did not put http:// in front of the address that names a port" \
  lacks "${CHECK_PREFIX} http://172.30.1.253:4000" "${LAST_SBX_LOG}"
assert "asked once per address and no more" \
  test "$(count "sbx policy check network" "${LAST_SBX_LOG}")" -eq 6
assert "never used a form the sandbox tool does not have" \
  lacks "sbx policy ls" "${LAST_SBX_LOG}"
assert "never used a form the sandbox tool does not have" \
  lacks "sbx policy show" "${LAST_SBX_LOG}"

# --- S4a: every address already allowed -> nothing is added ------------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_DENIED="" \
  run_case "S4a every address already allowed -> no rule is added"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "added no rules at all" lacks "sbx policy allow network" "${LAST_SBX_LOG}"
assert "said plainly that the rules were already there" \
  has "outbound network rules already in place" "${LAST_OUT}"
assert "still ran the deploy inside" has_line "${EXPECT_EXEC}" "${LAST_SBX_LOG}"

# --- S4b: one address not allowed -> the whole list is added, once -----------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_DENIED="http://files.pythonhosted.org" \
  run_case "S4b one address not allowed -> the whole list added once"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "added the rules with exactly the profile's list, comma-joined" \
  has_line "${EXPECT_ALLOW}" "${LAST_SBX_LOG}"
assert "added them exactly once" \
  test "$(count "sbx policy allow network" "${LAST_SBX_LOG}")" -eq 1
assert "said which address was missing, in plain words" \
  has "not yet allowed to reach http://files.pythonhosted.org" "${LAST_OUT}"

# --- S4c: the first address not allowed -> still exactly one call ------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_DENIED="http://deb.debian.org" \
  run_case "S4c the first address not allowed -> one call, the whole list"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "added the whole list, not just the missing address" \
  has_line "${EXPECT_ALLOW}" "${LAST_SBX_LOG}"
assert "added them exactly once" \
  test "$(count "sbx policy allow network" "${LAST_SBX_LOG}")" -eq 1
assert "stopped asking as soon as it knew it had to add them" \
  test "$(count "sbx policy check network" "${LAST_SBX_LOG}")" -eq 1

# --- S4d: nothing asked for -> nothing asked about, nothing added ------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_DENIED="" \
  run_case "S4d no addresses in the profile -> no policy calls at all"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "asked about nothing" lacks "sbx policy check network" "${LAST_SBX_LOG}"
assert "added nothing" lacks "sbx policy allow network" "${LAST_SBX_LOG}"
assert "still ran the deploy inside" has_line "${EXPECT_EXEC}" "${LAST_SBX_LOG}"

# --- S4e: nothing is allowed yet -> one call, still exactly one -------------
# This is also what happens when the sandbox tool cannot answer the question at
# all: a non-zero answer means "not allowed", and the safe move is to add the
# rules, which costs nothing if they are already there.
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_DENIED="${S_ALLOW_ASKED}" \
  run_case "S4e nothing allowed yet -> the rules are added once"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "added the rules once" \
  test "$(count "sbx policy allow network" "${LAST_SBX_LOG}")" -eq 1
assert "added the rules with exactly the profile's list, comma-joined" \
  has_line "${EXPECT_ALLOW}" "${LAST_SBX_LOG}"

# --- S5: the keeper is started ----------------------------------------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="" FAKE_SBX_DENIED="" \
  run_case "S5 the keeper is started for this sandbox"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "started the keeper as a user service, named for this sandbox" \
  has_line "${EXPECT_KEEPER}" "${LAST_SYSTEMCTL_LOG}"
assert "started nothing else" \
  test "$(count "systemctl" "${LAST_SYSTEMCTL_LOG}")" -eq 1
assert "never stopped or disabled anything" lacks "stop" "${LAST_SYSTEMCTL_LOG}"

# --- S6: the inner run, exact arguments and a real mode signal ---------------
CANDIDATE=1 CANDIDATE_PORT=8902 ROLLBACK_IMAGE_REF="apitest-app:rollback-pre-deploy" \
  SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_DENIED="" \
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

# --- S7: the order of the steps ---------------------------------------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="" FAKE_SBX_DENIED="http://pypi.org" \
  run_case "S7 create, then ask about the addresses, then keeper, then deploy"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "creates the sandbox BEFORE it asks whether the addresses are allowed" \
  before "sbx create" "sbx policy check network" "${LAST_SBX_LOG}"
assert "asks before it adds" \
  before "sbx policy check network" "sbx policy allow network" "${LAST_SBX_LOG}"
assert "adds the rules before it runs the deploy" \
  before "sbx policy allow network" "sbx exec" "${LAST_SBX_LOG}"
assert "starts the keeper before it runs the deploy" \
  before "starting the keeper" "running deploy/deploy.sh inside" "${LAST_OUT}"

# --- S8: the inner exit code is passed through, verbatim ---------------------
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_DENIED="" FAKE_SBX_EXEC_RC=0 \
  run_case "S8a the inner deploy succeeds -> exit 0"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "reported the inner exit code" has "exited 0" "${LAST_OUT}"

SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="${S_NAME}" FAKE_SBX_DENIED="" FAKE_SBX_EXEC_RC=3 \
  run_case "S8b the inner deploy fails with 3 -> exit 3, not 1"
assert "exit 3, the inner code exactly" test "${LAST_RC}" -eq 3
assert "reported the inner exit code" has "exited 3" "${LAST_OUT}"

# --- S9: no sandbox named -> refuse loudly, do nothing -----------------------
SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="" FAKE_SBX_DENIED="" \
  run_case "S9 no sandbox named -> refuses, touches nothing"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "says plainly what is missing and that it is refusing" \
  has "FATAL: SANDBOX_NAME is not set" "${LAST_OUT}"
assert "ran no sbx at all" lacks "sbx" "${LAST_SBX_LOG}"
assert "started no service at all" lacks "systemctl" "${LAST_SYSTEMCTL_LOG}"

# --- S10: the wrapper keeps no note of its own -------------------------------
# It used to write a marker file when it could not ask the sandbox tool about
# the rules. It asks the tool now, so there is nothing to remember and nothing
# to leave behind.
assert "no leftover note directory before the run" \
  test ! -e "${REPO_ROOT}/.guardkit/tmp"
SANDBOX_NAME="${S_NAME}" SANDBOX_MEMORY="${S_MEMORY}" SANDBOX_CPUS="${S_CPUS}" \
  SANDBOX_PUBLISH="${S_PUBLISH}" SANDBOX_ALLOW_NETWORK="${S_ALLOW}" \
  FAKE_SBX_LS="" FAKE_SBX_DENIED="http://pypi.org" \
  run_case "S10 a full run, rules added -> still writes no note"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "wrote nothing under .guardkit/" test ! -e "${REPO_ROOT}/.guardkit/tmp"
_WRAPPER_TEXT="$(cat "${WRAPPER}")"
assert "the wrapper does not mention .guardkit anywhere" \
  lacks ".guardkit" "${_WRAPPER_TEXT}"

# --- S11: the profile and the wrapper agree, and the wrapper is shared -------
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
# The same file ships as forge's template for a newly registered repository, so
# it must name no repository: every value it uses comes from the environment or
# from where the file itself sits.
assert "the wrapper names no repository, so the same bytes serve every one" \
  test "$(printf '%s\n' "${_WRAPPER_TEXT}" | grep -ciE 'api[-_]?test')" -eq 0

# --- summary -----------------------------------------------------------------
echo "================================"
echo "PASS=${PASS} FAIL=${FAIL}"
if [[ "${FAIL}" -ne 0 ]]; then
  exit 1
fi
echo "ALL SANDBOX-DEPLOY TESTS PASSED"
