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
#                      never touched (design §3 candidate-then-promote). It then
#                      READS THE BUILT IMAGE'S OWN ID and names it with the
#                      identity forge handed over, and prints both.
#   * Promote         : $PROMOTE truthy       -> snapshot the current LIVE image as
#                      the rollback tag, re-tag THE RECORDED ARTIFACT ($DEPLOY_ARTIFACT,
#                      an image id, never a shared tag) as the live image (NO
#                      rebuild), then live `up -d --no-build`, wait for health on the
#                      live port, and INSPECT THE RUNNING CONTAINER to say what is
#                      actually running.
#   * What is running : $RUNNING_IDENTITY truthy -> read-only. Inspects the live
#                      container and prints what it is running. Changes NOTHING.
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

# Echo the image id for a ref, or empty string if the ref is absent. The ref may
# itself be an image ID: docker resolves those too, which is the whole point --
# an ID is the one name in this system that cannot be moved onto another image.
image_id() {
  docker image inspect --format '{{.Id}}' "$1" 2>/dev/null || true
}

# The image reference that names ONE artifact and can never be given to another:
# the prefix this project uses, plus the identity forge handed over with its one
# '@' turned into a dash (an image reference may not carry '@' in a tag).
identity_ref() {
  printf '%s:%s\n' "${IDENTITY_IMAGE_PREFIX:-apitest-app}" "${1//@/-}"
}

# The container id currently serving the LIVE compose project's app service, or
# empty when nothing is up. `ps -q` is compose's own answer to "what is running".
live_container() {
  docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" ps -q app 2>/dev/null \
    | head -n1 || true
}

# The image id a RUNNING container was started from -- read off the container
# itself, never off a tag. This is the line that makes "what is running" a fact
# rather than a repetition of what this script was told: a tag can be moved onto
# another image after the container started; the container's own image id cannot.
running_image_id() {
  local cid="$1"
  [[ -z "${cid}" ]] && return 0
  docker inspect --format '{{.Image}}' "${cid}" 2>/dev/null || true
}

# The identity name carried by an image id, worked out from the identity-prefixed
# tags that image has. Empty when the image carries none -- which forge reads as
# "this target cannot be accounted for", and it then deploys nothing.
#
# The identity text is "<name>@<fingerprint>" and the tag is "<name>-<fingerprint>",
# where the fingerprint carries no dash, so the LAST dash is the one that was the
# '@'. Nothing else in this file needs to know the shape of an identity.
identity_of_image() {
  local id="$1" tags tag body
  [[ -z "${id}" ]] && return 0
  tags="$(docker image inspect --format '{{range .RepoTags}}{{println .}}{{end}}' \
    "${id}" 2>/dev/null || true)"
  while IFS= read -r tag; do
    [[ -z "${tag}" ]] && continue
    case "${tag}" in
      "${IDENTITY_IMAGE_PREFIX:-apitest-app}":*) ;;
      *) continue ;;
    esac
    body="${tag#*:}"
    case "${body}" in
      rollback-* | latest) continue ;;
    esac
    [[ "${body}" != *-* ]] && continue
    printf '%s@%s\n' "${body%-*}" "${body##*-}"
    return 0
  done <<<"${tags}"
  return 0
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
  #
  # WHAT CHANGED HERE (24 September 2026, the second review of the executor
  # stage). The promote used to make the unique name FROM the shared candidate
  # name, AT PROMOTE TIME. Between this check and that promote a second build's
  # candidate leg re-points ${CANDIDATE_APP_IMAGE} at ITS image, so the promote
  # named somebody else's build with this build's identity and put it live while
  # reporting this build's identity back. The window was real and it was driven.
  #
  # The cure is here, not there: the thing that was checked is pinned AT THE
  # MOMENT IT WAS CHECKED. This leg reads the built image's OWN ID -- the one
  # name in docker nothing can move onto another image -- gives it the identity's
  # tag immediately, and prints the id. Forge records that id, and the promote is
  # handed it back and resolves THAT, never the shared name.
  local cand_id checked_ref
  HEALTH_URL="http://localhost:${CANDIDATE_PORT}/health"
  log "MODE=candidate project=${CANDIDATE_PROJECT} port=${CANDIDATE_PORT} app_image=${CANDIDATE_APP_IMAGE}"
  log "candidate is a throwaway sandbox: no rollback snapshot, the LIVE name is untouched"
  docker compose -p "${CANDIDATE_PROJECT}" \
    -f "${COMPOSE_FILE}" -f "${CANDIDATE_COMPOSE_FILE}" up -d --build
  wait_for_health
  cand_id="$(image_id "${CANDIDATE_APP_IMAGE}")"
  if [[ -z "${cand_id}" ]]; then
    log "FATAL: the candidate came up but ${CANDIDATE_APP_IMAGE} names no image, so there is nothing whose identity could be captured. Refusing (LIVE untouched)"
    return 1
  fi
  if [[ -n "${DEPLOY_IDENTITY:-}" ]]; then
    # PIN IT NOW, under a name nothing else can be given.
    checked_ref="$(identity_ref "${DEPLOY_IDENTITY}")"
    docker tag "${cand_id}" "${checked_ref}"
    log "named what is being checked: ${checked_ref}=$(image_id "${checked_ref}")"
  else
    log "no DEPLOY_IDENTITY was handed to this check, so the artifact is reported by its own id alone"
  fi
  log "after: ${CANDIDATE_APP_IMAGE}=${cand_id}"
  # THE LINE FORGE READS BACK AND RECORDS. It is the artifact's own immutable
  # identity, captured here, and it is what the promote will be handed.
  printf 'CHECKED_ARTIFACT=%s\n' "${cand_id}"
  log "candidate up + healthy on :${CANDIDATE_PORT}"
}

running_identity() {
  # READ-ONLY. Forge asks this before it decides whether to deploy anything, so
  # that a decision is made against what the target is ACTUALLY running rather
  # than against a line in forge's own ledger that a crash may have left stale.
  # It changes nothing: no tag is moved, no compose project is brought up or
  # down, and it is safe to run at any time.
  # THE ANSWER IS ONE LINE, and forge reads exactly three things into it:
  #   RUNNING_IDENTITY=<token>  -- that is what is running here
  #   RUNNING_IDENTITY=         -- NOTHING is running here
  #   (no line at all)          -- this project did not answer
  # So "something is up but I cannot name it" must NOT print an empty value:
  # it prints a token forge cannot place, and forge then deploys nothing.
  local cid running identity
  cid="$(live_container)"
  if [[ -z "${cid}" ]]; then
    log "MODE=running-identity project=${COMPOSE_PROJECT}: nothing is up"
    printf 'RUNNING_IDENTITY=\n'
    return 0
  fi
  running="$(running_image_id "${cid}")"
  identity="$(identity_of_image "${running}")"
  log "MODE=running-identity project=${COMPOSE_PROJECT} container=${cid} image=${running:-<unknown>}"
  printf 'RUNNING_ARTIFACT=%s\n' "${running}"
  if [[ -z "${identity}" ]]; then
    # Something IS running and this project cannot say which build it is: the
    # image carries no identity tag. Answering empty here would tell forge the
    # target is free, which is the opposite of the truth.
    log "the running image carries no identity of this project's own"
    printf 'RUNNING_IDENTITY=unidentified-%s\n' "${running:-no-image}"
    return 0
  fi
  printf 'RUNNING_IDENTITY=%s\n' "${identity}"
}

deploy_promote() {
  # Promote to LIVE the exact artifact forge checked -- named by its own
  # immutable id, captured at the check -- and then say what is running by
  # INSPECTING THE RUNNING CONTAINER.
  #
  # WHY THIS CHANGED, TWICE.
  #
  # 23 September 2026 (forge's one-true-copy design pass, item 1, second
  # revision section C). This used to re-tag one shared candidate name --
  # ${CANDIDATE_APP_IMAGE} -- as the live tag. That name is SHARED: a second
  # build's candidate leg overwrites it.
  #
  # 24 September 2026, after the stage's second review. The first cure was not
  # a cure. It still READ THE SHARED NAME, at promote time, and only then gave
  # what it found the identity's tag. So a second build that replaced the
  # shared name between the check and this promote had ITS image given THIS
  # build's identity, put live, and reported back as this build's identity --
  # which was driven with a fake docker and is the exact failure the design
  # exists to prevent. Making a unique name out of a shared one, late, is not
  # capturing an identity.
  #
  # The artifact is captured WHERE IT IS CHECKED (deploy_candidate above), by
  # its own image id. Forge records that id and hands it back here as
  # $DEPLOY_ARTIFACT. This leg:
  #
  #   1. resolves $DEPLOY_ARTIFACT and refuses unless it is still exactly that
  #      artifact. The shared candidate name is NEVER read here;
  #   2. promotes THAT artifact by its id;
  #   3. asks the LIVE CONTAINER which image it is running, and reports the
  #      identity only when that container's own image id is the recorded
  #      artifact.
  #
  # Forge compares the reported line, as text, with the identity it handed
  # over; anything but an exact match is a FAILED deploy. Forge knows nothing
  # about images: what an identity IS belongs here, to the project.
  local artifact cur_id promoted_ref cid live_running running
  if [[ -z "${DEPLOY_IDENTITY:-}" ]]; then
    log "FATAL: no DEPLOY_IDENTITY was handed to this promote. This script promotes the exact thing that was checked, by an identity that cannot be reused; promoting the shared candidate name instead is the defect this refuses. (LIVE untouched)"
    return 1
  fi
  if [[ -z "${DEPLOY_ARTIFACT:-}" ]]; then
    log "FATAL: no DEPLOY_ARTIFACT was handed to this promote. The artifact is captured when the candidate is CHECKED and recorded by forge; without it this leg would have to resolve the shared candidate name, which is exactly the defect it refuses. (LIVE untouched)"
    return 1
  fi
  log "MODE=promote project=${COMPOSE_PROJECT} identity=${DEPLOY_IDENTITY} artifact=${DEPLOY_ARTIFACT} -> live_image=${APP_IMAGE}"
  # 0) RESOLVE THE RECORDED ARTIFACT, BY ITS OWN ID. An id resolves to itself
  #    or to nothing; it cannot resolve to somebody else's build.
  artifact="$(image_id "${DEPLOY_ARTIFACT}")"
  if [[ -z "${artifact}" ]]; then
    log "FATAL: the artifact that was checked (${DEPLOY_ARTIFACT}) is not here any more -- it cannot be promoted, and the shared candidate name is not a substitute for it. (LIVE untouched)"
    return 1
  fi
  if [[ "${artifact}" != "${DEPLOY_ARTIFACT}" ]]; then
    log "FATAL: ${DEPLOY_ARTIFACT} now resolves to ${artifact}, which is a different image -- refusing to promote something other than what was checked. (LIVE untouched)"
    return 1
  fi
  # 1) Re-assert the identity's own name on that artifact, so a person reading
  #    the running thing's labels can see where it came from. It is a name for
  #    the SAME image; nothing is resolved through it.
  promoted_ref="$(identity_ref "${DEPLOY_IDENTITY}")"
  docker tag "${artifact}" "${promoted_ref}"
  log "the checked artifact ${artifact} is named ${promoted_ref}"
  cur_id="$(image_id "${APP_IMAGE}")"
  # 2) Snapshot the current LIVE build as the rollback tag BEFORE we overwrite it.
  if [[ -n "${cur_id}" ]]; then
    docker tag "${APP_IMAGE}" "${ROLLBACK_IMAGE_REF}"
    log "snapshotted rollback: ${ROLLBACK_IMAGE_REF}=$(image_id "${ROLLBACK_IMAGE_REF}")"
  else
    docker tag "${APP_IMAGE}" "${ROLLBACK_IMAGE_REF}" || true
    log "no current ${APP_IMAGE} to snapshot (first promote)"
  fi
  # 3) Give the live tag to THE RECORDED ARTIFACT, by id -- NO rebuild.
  docker tag "${artifact}" "${APP_IMAGE}"
  log "promoted artifact: ${artifact} -> ${APP_IMAGE}=$(image_id "${APP_IMAGE}")"
  # 4) Bring the LIVE project up on the promoted image WITHOUT rebuilding.
  docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" up -d --no-build
  wait_for_health
  # 5) SAY WHAT IS RUNNING, read off the RUNNING CONTAINER. A tag says what a
  #    name points at now; the container says what it was started from, which
  #    is the only thing that answers "what is running".
  cid="$(live_container)"
  live_running="$(running_image_id "${cid}")"
  if [[ -n "${live_running}" && "${live_running}" == "${artifact}" ]]; then
    running="${DEPLOY_IDENTITY}"
  else
    running="not-${DEPLOY_IDENTITY}"
    log "WARNING: the live container ${cid:-<none>} is running ${live_running:-<unknown>}, not the artifact that was checked (${artifact})"
  fi
  log "after: container=${cid:-<none>} image=${live_running:-<unknown>} (checked artifact ${artifact})"
  # THE TWO LINES FORGE READS BACK. The first is the identity comparison the
  # press fails a deploy on; the second is the artifact, for the record.
  printf 'DEPLOYED_ARTIFACT=%s\n' "${live_running}"
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
  if is_truthy RUNNING_IDENTITY; then modes+=("running_identity"); fi
  if ((${#modes[@]} > 1)); then
    log "FATAL: ambiguous mode signal (${modes[*]}); set EXACTLY ONE of REVERT / CANDIDATE / PROMOTE / CANDIDATE_DOWN / RUNNING_IDENTITY (or none for a normal deploy). Refusing."
    return 2
  fi
  case "${modes[0]:-normal}" in
    revert) deploy_revert ;;
    candidate) deploy_candidate ;;
    promote) deploy_promote ;;
    candidate_down) candidate_down ;;
    running_identity) running_identity ;;
    normal) deploy_normal ;;
  esac
}

main() {
  log "repo_root=${REPO_ROOT}"
  resolve_and_run
}

main "$@"
