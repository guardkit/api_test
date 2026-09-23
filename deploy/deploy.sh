#!/usr/bin/env bash
#
# api_test vetted deploy script (the wrapper forge's deploy_compose step runs).
#
# CONTRACT (forge.executor.shell_steps.deploy_compose / _run_script_step):
#   * The script is invoked as a bare subprocess with NO argv:
#       subprocess.run([program], cwd=<step.params["cwd"]>, env=<os.environ (+ ENV_FILE)>)
#     so ALL inputs arrive via the ENVIRONMENT, never via command-line args.
#   * `cwd` is the profile's `cwd` (deploy/profile.yaml -> cwd:). We ALSO self-
#     anchor to the repo root via BASH_SOURCE so the compose file is found even
#     if the caller's cwd differs.
#   * `env_file` (profile compose.env_file) is exposed as $ENV_FILE (a PATH; the
#     runner never reads it — we source it here if present). This profile sets no
#     env_file, so $ENV_FILE is normally unset.
#
# MODE SIGNAL (see the C4 blocker note below). Exactly ONE mode env may be
# truthy; two or more is refused LOUDLY (deny-by-default, no guessing):
#   * Normal deploy  : all mode envs unset/false -> snapshot current image as the
#                      rollback tag, then `up -d --build`, then wait for health.
#   * O-32 revert     : $REVERT truthy       -> re-tag $ROLLBACK_IMAGE_REF as the
#                      compose image tag, then `up -d --no-build` (the ROLLBACK
#                      image serves), then wait for health.
#   * Candidate       : $CANDIDATE truthy    -> bring a THROWAWAY sandbox copy up
#                      on the -cand project (offset host port $CANDIDATE_PORT) with
#                      the candidate overlay, `up -d --build`, wait for health on
#                      the candidate port. NO rollback snapshot; the LIVE name is
#                      never touched (design §3 candidate-then-promote).
#   * Promote         : $PROMOTE truthy       -> snapshot the current LIVE image as
#                      the rollback tag, RE-TAG the candidate-built image as the
#                      live image (NO rebuild), then live `up -d --no-build`, wait
#                      for health on the live port.
#   * Candidate down  : $CANDIDATE_DOWN truthy -> `down -v --remove-orphans` on the
#                      -cand project (teardown of the sandbox + its db volume).
#
#   The forge revert runbook (runbook_builder.build_revert_runbook) puts
#   `revert: True` and `rollback_image_ref` in the deploy_compose STEP PARAMS;
#   shell_steps.deploy_compose threads them to this script as REVERT=1 and
#   ROLLBACK_IMAGE_REF=<tag> (forge commit deff3c4f, 2026-07-16 — the O-32
#   revert-signal fix this lane surfaced). The revert logic below is proven by
#   deploy/tests/run_deploy_tests.sh against a PATH-shimmed fake docker.
#
# SAFETY: this script is EXECUTED ONLY BY FORGE AT C4 (attended). It is proven
# in this lane with a PATH-shimmed fake docker/curl harness, never run against
# the live apitest-f2 project here.
set -euo pipefail

# --- anchor to the repo root (where docker-compose.yml lives) ----------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# --- config (env-overridable; defaults are the live apitest-f2 layout) -------
COMPOSE_PROJECT="${COMPOSE_PROJECT:-apitest-f2}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
# The image the `app` service resolves to. The compose `app` service has
# `build: .` and no explicit `image:`, so compose names the built image
# <project>-<service> = apitest-f2-app:latest (verified against the live stack).
APP_IMAGE="${APP_IMAGE:-apitest-f2-app:latest}"
# The kept rollback tag this script maintains; MUST match profile.rollback_image_ref.
ROLLBACK_IMAGE_REF="${ROLLBACK_IMAGE_REF:-apitest-app:rollback-pre-deploy}"
# --- candidate-then-promote sandbox config (design §3) -----------------------
# Offset host port the candidate publishes (verified free; convention = 8902).
CANDIDATE_PORT="${CANDIDATE_PORT:-8902}"
# The -cand compose project: a lifecycle namespace with its OWN network + db.
CANDIDATE_PROJECT="${CANDIDATE_PROJECT:-${COMPOSE_PROJECT}-cand}"
# The candidate overlay layered on top of $COMPOSE_FILE (remaps the app port).
CANDIDATE_COMPOSE_FILE="${CANDIDATE_COMPOSE_FILE:-deploy/docker-compose.candidate.yml}"
# The image `docker compose -p <cand project> build` produces for the app service:
# compose names build-only images <project>-<service>, so apitest-f2-cand-app:latest.
# PROMOTE re-tags THIS as $APP_IMAGE so the live `up --no-build` serves it.
CANDIDATE_APP_IMAGE="${CANDIDATE_APP_IMAGE:-${CANDIDATE_PROJECT}-app:latest}"
# Health wait (curl the app /health until it reports the DB connected).
HEALTH_URL="${HEALTH_URL:-http://localhost:8901/health}"
HEALTH_EXPECT="${HEALTH_EXPECT:-\"database\":\"connected\"}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-120}"
HEALTH_INTERVAL_SECONDS="${HEALTH_INTERVAL_SECONDS:-3}"

# Optional env file (forge exposes its PATH via $ENV_FILE); source if present.
if [[ -n "${ENV_FILE:-}" && -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
fi

log() { printf '[deploy.sh] %s\n' "$*"; }

# Echo the image id for a ref, or empty string if the ref is absent.
image_id() {
  docker image inspect --format '{{.Id}}' "$1" 2>/dev/null || true
}

# Truthy test for the env var NAMED by $1 (indirect expansion), so one helper
# serves every mode flag: REVERT / CANDIDATE / PROMOTE / CANDIDATE_DOWN.
is_truthy() {
  case "${!1:-}" in
    1 | true | TRUE | yes | YES) return 0 ;;
    *) return 1 ;;
  esac
}

# Poll HEALTH_URL until the body contains HEALTH_EXPECT; fail loud on timeout.
wait_for_health() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
  local body=""
  log "waiting for health: ${HEALTH_URL} to contain [${HEALTH_EXPECT}] (timeout ${HEALTH_TIMEOUT_SECONDS}s)"
  while ((SECONDS < deadline)); do
    if body="$(curl -fsS "${HEALTH_URL}" 2>/dev/null)" \
      && printf '%s' "${body}" | grep -qF -- "${HEALTH_EXPECT}"; then
      log "health OK: ${body}"
      return 0
    fi
    sleep "${HEALTH_INTERVAL_SECONDS}"
  done
  log "FATAL: ${HEALTH_URL} did not become healthy within ${HEALTH_TIMEOUT_SECONDS}s"
  return 1
}

deploy_normal() {
  local cur_id
  cur_id="$(image_id "${APP_IMAGE}")"
  log "MODE=normal project=${COMPOSE_PROJECT} app_image=${APP_IMAGE}"
  log "before: ${APP_IMAGE}=${cur_id:-<none>} rollback=${ROLLBACK_IMAGE_REF}=$(image_id "${ROLLBACK_IMAGE_REF}")"
  if [[ -n "${cur_id}" ]]; then
    # Snapshot the currently-running build as the rollback image BEFORE we
    # replace it, so an O-32 revert can bring the prior build back up.
    docker tag "${APP_IMAGE}" "${ROLLBACK_IMAGE_REF}"
    log "snapshotted rollback: ${ROLLBACK_IMAGE_REF}=$(image_id "${ROLLBACK_IMAGE_REF}")"
  else
    # First-ever deploy: nothing running to snapshot (|| true per the contract).
    docker tag "${APP_IMAGE}" "${ROLLBACK_IMAGE_REF}" || true
    log "no current ${APP_IMAGE} to snapshot (first deploy)"
  fi
  docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" up -d --build
  wait_for_health
  log "after: ${APP_IMAGE}=$(image_id "${APP_IMAGE}")"
  log "deploy complete"
}

deploy_revert() {
  local rb_id
  rb_id="$(image_id "${ROLLBACK_IMAGE_REF}")"
  log "MODE=revert project=${COMPOSE_PROJECT} rollback_image_ref=${ROLLBACK_IMAGE_REF}"
  if [[ -z "${rb_id}" ]]; then
    # Loud terminal failure: no kept image to revert to (mirrors forge's own
    # missing-rollback loud fail in stage._run_revert).
    log "FATAL: rollback image ${ROLLBACK_IMAGE_REF} not found -- cannot revert; refusing to keep serving the unverified build"
    return 1
  fi
  log "before: ${APP_IMAGE}=$(image_id "${APP_IMAGE}") rollback=${ROLLBACK_IMAGE_REF}=${rb_id}"
  # Re-tag the kept rollback image as the compose image tag so `up --no-build`
  # brings the ROLLBACK image up (no rebuild -- we re-serve a known-good image).
  docker tag "${ROLLBACK_IMAGE_REF}" "${APP_IMAGE}"
  log "re-tagged ${ROLLBACK_IMAGE_REF} -> ${APP_IMAGE}=$(image_id "${APP_IMAGE}")"
  docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" up -d --no-build
  wait_for_health
  log "after: ${APP_IMAGE}=$(image_id "${APP_IMAGE}") (serving rollback ${rb_id})"
  log "revert complete"
}

deploy_candidate() {
  # A throwaway sandbox copy on the -cand project + offset host port. NO rollback
  # snapshot is taken and the LIVE image/name is NEVER touched: a failing
  # candidate is simply torn down (candidate_down) with the live leg untouched.
  # Health is probed on the CANDIDATE port (the app still listens on 8901 inside
  # the container; only the host publish moves).
  HEALTH_URL="http://localhost:${CANDIDATE_PORT}/health"
  log "MODE=candidate project=${CANDIDATE_PROJECT} port=${CANDIDATE_PORT} app_image=${CANDIDATE_APP_IMAGE}"
  log "candidate is a throwaway sandbox: no rollback snapshot, the LIVE name is untouched"
  docker compose -p "${CANDIDATE_PROJECT}" \
    -f "${COMPOSE_FILE}" -f "${CANDIDATE_COMPOSE_FILE}" up -d --build
  wait_for_health
  log "after: ${CANDIDATE_APP_IMAGE}=$(image_id "${CANDIDATE_APP_IMAGE}")"
  log "candidate up + healthy on :${CANDIDATE_PORT}"
}

deploy_promote() {
  # Promote to LIVE the exact thing forge checked, named by an identity that
  # cannot be reused, and then SAY what is running.
  #
  # WHY THIS CHANGED (23 September 2026; forge's one-true-copy design pass,
  # item 1, second revision section C). This used to re-tag one shared
  # candidate name -- ${CANDIDATE_APP_IMAGE} -- as the live tag. That name is
  # SHARED: a second build's candidate leg overwrites it. So between forge
  # checking a thing and this script promoting it, the name could already
  # point at somebody else's build, and the promote would put THAT live under
  # the first build's sentence. The name was the defect.
  #
  # Now forge hands this script $DEPLOY_IDENTITY -- text it made from the
  # joined commit it checked, with a fingerprint of that content beside it --
  # and this script:
  #
  #   1. tags the candidate image with that identity FIRST, so the thing being
  #      promoted has a name nothing else can be given;
  #   2. promotes THAT tag, never the shared one;
  #   3. prints DEPLOYED_IDENTITY=<what is actually running>, worked out by
  #      comparing the live tag's image id with the identity tag's rather than
  #      by repeating what it was told.
  #
  # Forge compares the two as text, and a mismatch is a FAILED deploy. Forge
  # knows nothing about images: what an identity IS belongs here, to the
  # project, and here it is an image tag plus that image's own id.
  #
  # Called with no $DEPLOY_IDENTITY -- by hand, or by a forge from before this
  # -- it REFUSES rather than falling back to the shared name, because the
  # shared name is exactly what this change removes.
  local cand_id cur_id promoted_ref live_id running
  if [[ -z "${DEPLOY_IDENTITY:-}" ]]; then
    log "FATAL: no DEPLOY_IDENTITY was handed to this promote. This script promotes the exact thing that was checked, by an identity that cannot be reused; promoting the shared candidate name instead is the defect this refuses. (LIVE untouched)"
    return 1
  fi
  cand_id="$(image_id "${CANDIDATE_APP_IMAGE}")"
  log "MODE=promote project=${COMPOSE_PROJECT} identity=${DEPLOY_IDENTITY} candidate_image=${CANDIDATE_APP_IMAGE} -> live_image=${APP_IMAGE}"
  if [[ -z "${cand_id}" ]]; then
    # Loud terminal failure: nothing to promote. The candidate leg never built
    # (or was torn down). The LIVE name is untouched.
    log "FATAL: candidate image ${CANDIDATE_APP_IMAGE} not found -- run the CANDIDATE leg first; refusing to promote (LIVE untouched)"
    return 1
  fi
  # 0) GIVE WHAT WAS CHECKED ITS OWN NAME, before anything else is touched.
  #    The identity's own characters are letters, digits, dots and dashes plus
  #    one '@' between the name and the fingerprint; only that '@' has to
  #    become a dash for an image reference.
  promoted_ref="${IDENTITY_IMAGE_PREFIX:-apitest-app}:${DEPLOY_IDENTITY//@/-}"
  docker tag "${CANDIDATE_APP_IMAGE}" "${promoted_ref}"
  log "named what was checked: ${promoted_ref}=$(image_id "${promoted_ref}")"
  cur_id="$(image_id "${APP_IMAGE}")"
  # 1) Snapshot the current LIVE build as the rollback tag BEFORE we overwrite it.
  if [[ -n "${cur_id}" ]]; then
    docker tag "${APP_IMAGE}" "${ROLLBACK_IMAGE_REF}"
    log "snapshotted rollback: ${ROLLBACK_IMAGE_REF}=$(image_id "${ROLLBACK_IMAGE_REF}")"
  else
    docker tag "${APP_IMAGE}" "${ROLLBACK_IMAGE_REF}" || true
    log "no current ${APP_IMAGE} to snapshot (first promote)"
  fi
  # 2) Re-tag THE IDENTITY'S OWN IMAGE as the live image tag -- NO rebuild.
  #    This is the line that changed: it used to name the shared candidate.
  docker tag "${promoted_ref}" "${APP_IMAGE}"
  log "promoted image: ${promoted_ref} -> ${APP_IMAGE}=$(image_id "${APP_IMAGE}")"
  # 3) Bring the LIVE project up on the promoted image WITHOUT rebuilding.
  docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" up -d --no-build
  wait_for_health
  live_id="$(image_id "${APP_IMAGE}")"
  # 4) SAY WHAT IS RUNNING, read back rather than repeated. The live tag and
  #    the identity's own tag are the same image only if the promote really
  #    happened, so the identity is reported only when the two ids match.
  if [[ -n "${live_id}" && "${live_id}" == "$(image_id "${promoted_ref}")" ]]; then
    running="${DEPLOY_IDENTITY}"
  else
    running="not-${DEPLOY_IDENTITY}"
    log "WARNING: ${APP_IMAGE} is not the image ${promoted_ref} names"
  fi
  log "after: ${APP_IMAGE}=${live_id} (live serving ${promoted_ref}, candidate ${cand_id})"
  # THE ONE LINE FORGE READS BACK. Forge compares it, as text, with what it
  # handed over; anything but an exact match is a FAILED deploy.
  printf 'DEPLOYED_IDENTITY=%s\n' "${running}"
  log "promote complete"
}

candidate_down() {
  # Teardown helper: remove the -cand project + its db volume + orphans. Used
  # when a candidate gate FAILS (live never touched) or after a promote when
  # candidate.keep is false. The LIVE project is never named here.
  log "MODE=candidate_down project=${CANDIDATE_PROJECT} (tearing the sandbox down with volumes)"
  docker compose -p "${CANDIDATE_PROJECT}" \
    -f "${COMPOSE_FILE}" -f "${CANDIDATE_COMPOSE_FILE}" down -v --remove-orphans
  log "candidate ${CANDIDATE_PROJECT} torn down"
}

# Resolve the single active mode from the truthy flags; refuse ambiguity loudly.
resolve_and_run() {
  local modes=()
  if is_truthy REVERT; then modes+=("revert"); fi
  if is_truthy CANDIDATE; then modes+=("candidate"); fi
  if is_truthy PROMOTE; then modes+=("promote"); fi
  if is_truthy CANDIDATE_DOWN; then modes+=("candidate_down"); fi
  if ((${#modes[@]} > 1)); then
    log "FATAL: ambiguous mode signal (${modes[*]}); set EXACTLY ONE of REVERT / CANDIDATE / PROMOTE / CANDIDATE_DOWN (or none for a normal deploy). Refusing."
    return 2
  fi
  case "${modes[0]:-normal}" in
    revert) deploy_revert ;;
    candidate) deploy_candidate ;;
    promote) deploy_promote ;;
    candidate_down) candidate_down ;;
    normal) deploy_normal ;;
  esac
}

main() {
  log "repo_root=${REPO_ROOT}"
  resolve_and_run
}

main "$@"
