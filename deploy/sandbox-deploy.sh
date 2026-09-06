#!/usr/bin/env bash
#
# api_test sandbox deploy wrapper — the vetted script the forge deploy step runs
# for the compose stage (deploy/profile.yaml -> compose.script).
#
# WHAT IT IS FOR (Rich's decision, 2026-09-06). Every merge now deploys the
# feature into a Docker Sandbox: a small virtual machine with its own kernel and
# its own Docker engine, made by Docker's `sbx` tool. The host's own Docker
# engine is no longer in the deployment path. This wrapper is the only thing that
# knows about the sandbox; deploy/deploy.sh is unchanged and simply runs inside.
#
# WHAT IT DOES, IN ORDER, AND NOTHING ELSE:
#   1. Make sure this repository's sandbox exists. If `sbx ls` does not list it,
#      create it, bind-mounting this checkout at its own host path so the path is
#      the same inside the sandbox and out, with the memory, processor count and
#      published ports the profile asked for.
#   2. Add the outbound network rules once. The sandbox refuses every address it
#      has not been told about, so the image build needs the Debian mirrors and
#      the Python package index named explicitly.
#   3. Start the keeper, a small user service that holds one session open inside
#      the sandbox so it does not put itself to sleep thirty seconds after the
#      last session ends.
#   4. Run deploy/deploy.sh inside the sandbox and exit with its exit code,
#      unchanged, so a failing deploy still fails the stage.
#
# HOW IT IS CONFIGURED. Everything arrives in the environment, threaded in by the
# deploy stage from the profile's `sandbox` block. This script never reads YAML.
#   SANDBOX_NAME           the sandbox's name              (required)
#   SANDBOX_MEMORY         memory size, as `sbx` accepts it, e.g. 6g
#   SANDBOX_CPUS           how many processors, e.g. 4
#   SANDBOX_PUBLISH        ports handed back to the host, comma-separated
#   SANDBOX_ALLOW_NETWORK  addresses the sandbox may reach, comma-separated
#
# SAFETY. This script is run by forge at the attended deploy step. In the build
# lane it is proven against fake `sbx` and `systemctl` programs placed first on
# PATH (deploy/tests/run_sandbox_deploy_tests.sh); no real sandbox is ever
# created, started, stopped or removed by a build agent.
set -euo pipefail

# --- anchor to the repository root ------------------------------------------
# deploy/deploy.sh anchors itself the same way. This directory is also the
# profile's `cwd`, which is the path the checkout is bind-mounted at inside the
# sandbox, so it is what we hand to `sbx` for both the mount and the working
# directory of the inner run.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() { printf '[sandbox-deploy.sh] %s\n' "$*"; }

# --- settings from the environment ------------------------------------------
SANDBOX_NAME="${SANDBOX_NAME:-}"
SANDBOX_MEMORY="${SANDBOX_MEMORY:-}"
SANDBOX_CPUS="${SANDBOX_CPUS:-}"
SANDBOX_PUBLISH="${SANDBOX_PUBLISH:-}"
SANDBOX_ALLOW_NETWORK="${SANDBOX_ALLOW_NETWORK:-}"

if [[ -z "${SANDBOX_NAME}" ]]; then
  log "FATAL: SANDBOX_NAME is not set. This repository's deploy profile must carry a sandbox block naming the sandbox to deploy into, and the deploy stage must thread it in. Refusing to deploy."
  exit 2
fi

# The keeper is a user service, one instance per sandbox name.
KEEPER_UNIT="forge-sandbox-keeper@${SANDBOX_NAME}"

# Where we remember that the network rules have been applied. `sbx` may not be
# able to list the rules for one sandbox; when it cannot, this file is how we
# know not to apply them a second time. It is build-time state, not source: it
# lives under .guardkit/ with the rest of the machine-local build state and is
# never committed.
MARKER_DIR="${REPO_ROOT}/.guardkit/tmp"
MARKER_FILE="${MARKER_DIR}/sandbox-network-rules-${SANDBOX_NAME}"

# --- step 1: the sandbox exists ---------------------------------------------

# True when `sbx ls` names this sandbox. Matches a whole field so a sandbox
# called "api-test-deploy" is not confused with "api-test-deploy-2".
sandbox_exists() {
  local listing
  listing="$(sbx ls 2>/dev/null || true)"
  printf '%s\n' "${listing}" |
    awk -v name="${SANDBOX_NAME}" '{ for (i = 1; i <= NF; i++) if ($i == name) found = 1 } END { exit(found ? 0 : 1) }'
}

create_sandbox() {
  local argv=(sbx create shell "${REPO_ROOT}" --name "${SANDBOX_NAME}")
  if [[ -n "${SANDBOX_MEMORY}" ]]; then
    argv+=(--memory "${SANDBOX_MEMORY}")
  fi
  if [[ -n "${SANDBOX_CPUS}" ]]; then
    argv+=(--cpus "${SANDBOX_CPUS}")
  fi
  # One --publish for each entry in the comma-separated list.
  if [[ -n "${SANDBOX_PUBLISH}" ]]; then
    local entry
    local -a publishes=()
    IFS=',' read -r -a publishes <<<"${SANDBOX_PUBLISH}"
    for entry in "${publishes[@]}"; do
      if [[ -n "${entry}" ]]; then
        argv+=(--publish "${entry}")
      fi
    done
  fi
  log "creating sandbox ${SANDBOX_NAME} on ${REPO_ROOT}"
  "${argv[@]}"
}

# --- step 2: the network rules, once ----------------------------------------

# True when the rules are already in place. We ask `sbx` first: if it can list
# the rules for this sandbox and every rule we want is there, there is nothing to
# do. If `sbx` cannot answer that question, we fall back to the marker file.
network_rules_present() {
  if [[ -z "${SANDBOX_ALLOW_NETWORK}" ]]; then
    return 0 # nothing was asked for
  fi
  local listing rule
  local -a rules=()
  IFS=',' read -r -a rules <<<"${SANDBOX_ALLOW_NETWORK}"
  if listing="$(sbx policy ls --sandbox "${SANDBOX_NAME}" 2>/dev/null)"; then
    for rule in "${rules[@]}"; do
      if [[ -n "${rule}" ]] && ! printf '%s' "${listing}" | grep -qF -- "${rule}"; then
        return 1
      fi
    done
    return 0
  fi
  # `sbx` has no per-sandbox rule list on this version: use our own note.
  if [[ -f "${MARKER_FILE}" ]] && grep -qxF -- "${SANDBOX_ALLOW_NETWORK}" "${MARKER_FILE}"; then
    return 0
  fi
  return 1
}

allow_network() {
  log "allowing outbound addresses for ${SANDBOX_NAME}: ${SANDBOX_ALLOW_NETWORK}"
  sbx policy allow network --sandbox "${SANDBOX_NAME}" "${SANDBOX_ALLOW_NETWORK}"
  mkdir -p "${MARKER_DIR}"
  printf '%s\n' "${SANDBOX_ALLOW_NETWORK}" >"${MARKER_FILE}"
}

# --- step 4: the deploy itself, inside the sandbox --------------------------

# A bare `-e NAME` tells sbx to take that variable's value from this script's own
# environment, so the mode signal the deploy stage sets (a normal deploy, the
# candidate leg, promote, revert, or the candidate teardown) reaches deploy.sh
# inside the sandbox unchanged.
run_deploy_inside() {
  local rc=0
  log "running deploy/deploy.sh inside ${SANDBOX_NAME} (working directory ${REPO_ROOT})"
  sbx exec -w "${REPO_ROOT}" \
    -e CANDIDATE \
    -e PROMOTE \
    -e REVERT \
    -e CANDIDATE_DOWN \
    -e CANDIDATE_PORT \
    -e ROLLBACK_IMAGE_REF \
    -e ENV_FILE \
    "${SANDBOX_NAME}" deploy/deploy.sh || rc=$?
  return "${rc}"
}

main() {
  log "repo_root=${REPO_ROOT} sandbox=${SANDBOX_NAME}"

  if sandbox_exists; then
    log "sandbox ${SANDBOX_NAME} already exists"
  else
    create_sandbox
  fi

  if network_rules_present; then
    log "outbound network rules already in place for ${SANDBOX_NAME}"
  else
    allow_network
  fi

  log "starting the keeper so the sandbox stays awake: ${KEEPER_UNIT}"
  systemctl --user start "${KEEPER_UNIT}"

  local rc=0
  run_deploy_inside || rc=$?
  log "deploy/deploy.sh inside ${SANDBOX_NAME} exited ${rc}"
  exit "${rc}"
}

main "$@"
