"""The runtime round-trip oracle tests the code it was asked about (2026-09-06).

Regression case: until 2026-09-06 ``tests/acceptance/users_roundtrip.py`` built
``apitest-app:smoke`` only when the tag was missing, so every run after
2026-07-25 tested the image built that day. Build FEAT-8388 (2026-09-06)
changed the users model without a migration, the oracle passed against the
July image, and the deploy into the sandbox then found the fresh database had
no ``domain`` column. These tests pin the three things that fix it:

  1. ``_ensure_image`` builds on every run — a present tag no longer
     short-circuits the build — and returns the id the build produced.
  2. ``_deploy_stack`` proves the running ``app`` container uses that id, and
     a mismatch is a loud failure naming both ids.
  3. The schema in the smoke stack comes from ``alembic upgrade head`` in the
     image's entrypoint, never from ``create_all``.

No Docker, no network: ``subprocess.run`` is replaced by a fake that answers
the exact docker commands the oracle runs and refuses anything else.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORACLE_PATH = PROJECT_ROOT / "tests" / "acceptance" / "users_roundtrip.py"
ENTRYPOINT = PROJECT_ROOT / "docker-entrypoint.sh"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"
COMPOSE_FILE = PROJECT_ROOT / "deploy" / "docker-compose.smoke.yml"
SRC_DIR = PROJECT_ROOT / "src"
ALEMBIC_ENV = PROJECT_ROOT / "alembic" / "env.py"

JULY_IMAGE_ID = "sha256:" + "07" * 32  # the stale tag the old code kept reusing
FRESH_IMAGE_ID = "sha256:" + "09" * 32  # what this run's build produces
APP_CONTAINER_ID = "0123456789abcdef"


# ---------------------------------------------------------------------------
# The oracle module, loaded by path (tests/acceptance has no __init__.py)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def oracle() -> ModuleType:
    """Load the real oracle module so the tests exercise its actual code."""
    spec = importlib.util.spec_from_file_location("users_roundtrip_under_test", ORACLE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeDocker:
    """Stand-in for ``subprocess.run`` that answers the oracle's docker calls.

    It keeps a tag -> image id table and a container -> image id table, records
    every command (and the ``cwd`` of the build), and raises on any command the
    oracle is not expected to run so a drift in the oracle shows up here.
    """

    def __init__(
        self,
        *,
        images: dict[str, str] | None = None,
        containers: dict[str, str] | None = None,
        build_produces: str = FRESH_IMAGE_ID,
        build_exit: int = 0,
    ) -> None:
        self.images = dict(images or {})
        self.containers = dict(containers or {})
        self.build_produces = build_produces
        self.build_exit = build_exit
        self.calls: list[list[str]] = []
        self.build_cwd: str | None = None

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(list(cmd))
        if cmd[:2] == ["docker", "build"]:
            self.build_cwd = kwargs.get("cwd")
            if self.build_exit != 0:
                return self._done(cmd, self.build_exit, stderr=b"build exploded")
            tag = cmd[cmd.index("-t") + 1]
            self.images[tag] = self.build_produces
            return self._done(cmd, 0)
        if cmd[:3] == ["docker", "image", "inspect"]:
            tag = cmd[-1]
            if tag not in self.images:
                return self._done(cmd, 1, stderr=b"No such image")
            if "--format" in cmd:
                return self._done(cmd, 0, stdout=self.images[tag].encode() + b"\n")
            return self._done(cmd, 0, stdout=b"[]")
        if cmd[:2] == ["docker", "compose"] and "ps" in cmd:
            service = cmd[-1]
            assert service == "app", f"unexpected service in ps: {cmd}"
            ids = "\n".join(self.containers)
            return self._done(cmd, 0, stdout=(ids + "\n").encode() if ids else b"")
        if cmd[:2] == ["docker", "compose"] and "up" in cmd:
            return self._done(cmd, 0)
        if cmd[:2] == ["docker", "inspect"] and "{{.Image}}" in cmd:
            container = cmd[-1]
            if container not in self.containers:
                return self._done(cmd, 1, stderr=b"No such object")
            return self._done(cmd, 0, stdout=self.containers[container].encode() + b"\n")
        raise AssertionError(f"the oracle ran a docker command this fake does not expect: {cmd}")

    @staticmethod
    def _done(
        cmd: list[str], returncode: int, *, stdout: bytes = b"", stderr: bytes = b""
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    def build_calls(self) -> list[list[str]]:
        return [c for c in self.calls if c[:2] == ["docker", "build"]]


# ---------------------------------------------------------------------------
# Rule 18 / 21: build every run; a present tag no longer short-circuits
# ---------------------------------------------------------------------------


def test_present_tag_no_longer_short_circuits_the_build(
    oracle: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression case: the tag is present (the July image) and the build
    still runs, from the worktree root, and the fresh id is what comes back."""
    fake = FakeDocker(images={oracle.IMAGE_TAG: JULY_IMAGE_ID})
    monkeypatch.setattr(oracle.subprocess, "run", fake)

    built = oracle._ensure_image(time.monotonic())

    assert fake.build_calls() == [["docker", "build", "-t", oracle.IMAGE_TAG, "."]], (
        "a present tag must not skip the build"
    )
    assert fake.build_cwd == str(oracle.WORKTREE_ROOT), "the build runs from the worktree root"
    assert built == FRESH_IMAGE_ID
    assert built != JULY_IMAGE_ID
    assert fake.images[oracle.IMAGE_TAG] == FRESH_IMAGE_ID, "the tag now points at the fresh image"


def test_build_runs_first_and_the_id_is_read_after_it(
    oracle: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No inspect is consulted before the build; the id comes from after it."""
    fake = FakeDocker(images={oracle.IMAGE_TAG: JULY_IMAGE_ID})
    monkeypatch.setattr(oracle.subprocess, "run", fake)

    oracle._ensure_image(time.monotonic())

    assert fake.calls[0][:2] == ["docker", "build"], f"first docker call was {fake.calls[0]}"
    inspects = [c for c in fake.calls if c[:3] == ["docker", "image", "inspect"]]
    assert inspects == [
        ["docker", "image", "inspect", "--format", "{{.Id}}", oracle.IMAGE_TAG]
    ], "exactly one inspect, for the id, after the build"


def test_missing_tag_is_built_too(oracle: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """The original case (no tag at all) still builds and returns the new id."""
    fake = FakeDocker(images={})
    monkeypatch.setattr(oracle.subprocess, "run", fake)

    assert oracle._ensure_image(time.monotonic()) == FRESH_IMAGE_ID
    assert len(fake.build_calls()) == 1


def test_build_failure_is_a_loud_failure(
    oracle: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeDocker(images={oracle.IMAGE_TAG: JULY_IMAGE_ID}, build_exit=3)
    monkeypatch.setattr(oracle.subprocess, "run", fake)

    with pytest.raises(pytest.fail.Exception, match="docker build failed \\(exit 3\\)") as excinfo:
        oracle._ensure_image(time.monotonic())
    assert "build exploded" in str(excinfo.value)


def test_build_budget_is_still_120_seconds(oracle: ModuleType) -> None:
    assert oracle.IMAGE_BUILD_TIMEOUT == 120


# ---------------------------------------------------------------------------
# Rule 19: prove the running container is the image just built
# ---------------------------------------------------------------------------


def test_running_image_mismatch_fails_naming_both_ids(
    oracle: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The container came up on the July image while this run built a fresh one."""
    fake = FakeDocker(containers={APP_CONTAINER_ID: JULY_IMAGE_ID})
    monkeypatch.setattr(oracle.subprocess, "run", fake)

    with pytest.raises(pytest.fail.Exception) as excinfo:
        oracle._prove_running_image(FRESH_IMAGE_ID)

    message = str(excinfo.value)
    assert FRESH_IMAGE_ID in message, "the built id must be named"
    assert JULY_IMAGE_ID in message, "the running id must be named"
    assert "not running the image this run built" in message


def test_running_image_match_passes_and_prints_the_proof_line(
    oracle: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeDocker(containers={APP_CONTAINER_ID: FRESH_IMAGE_ID})
    monkeypatch.setattr(oracle.subprocess, "run", fake)

    oracle._prove_running_image(FRESH_IMAGE_ID)

    out = capsys.readouterr().out
    proof_lines = [line for line in out.splitlines() if "image proof" in line]
    assert len(proof_lines) == 1, out
    assert FRESH_IMAGE_ID in proof_lines[0] and proof_lines[0].endswith("match")
    # The id was read from the compose project's app container, not guessed.
    assert ["docker", "inspect", "--format", "{{.Image}}", APP_CONTAINER_ID] in fake.calls
    ps_calls = [c for c in fake.calls if c[:2] == ["docker", "compose"] and "ps" in c]
    assert ps_calls == [
        [
            "docker", "compose", "-p", oracle.SMOKE_PROJECT, "-f", str(oracle.COMPOSE_FILE),
            "ps", "-q", "-a", oracle.APP_SERVICE,
        ]
    ]


def test_no_app_container_is_a_loud_failure(
    oracle: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeDocker(containers={})
    monkeypatch.setattr(oracle.subprocess, "run", fake)

    with pytest.raises(pytest.fail.Exception, match="Expected exactly one 'app' container"):
        oracle._prove_running_image(FRESH_IMAGE_ID)


def test_deploy_stack_proves_the_image_before_waiting_for_health(
    oracle: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real ``_deploy_stack``: compose up, then the proof, then the health wait."""
    fake = FakeDocker(containers={APP_CONTAINER_ID: FRESH_IMAGE_ID})
    monkeypatch.setattr(oracle.subprocess, "run", fake)
    order: list[str] = []
    monkeypatch.setattr(oracle, "_wait_for_health", lambda start: order.append("health"))
    real_prove = oracle._prove_running_image
    monkeypatch.setattr(
        oracle, "_prove_running_image",
        lambda built: (order.append("proof"), real_prove(built)),
    )

    oracle._deploy_stack(time.monotonic(), FRESH_IMAGE_ID)

    assert order == ["proof", "health"]
    assert any(c[:2] == ["docker", "compose"] and "up" in c for c in fake.calls)


def test_deploy_stack_stops_on_a_mismatch_before_the_health_wait(
    oracle: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeDocker(containers={APP_CONTAINER_ID: JULY_IMAGE_ID})
    monkeypatch.setattr(oracle.subprocess, "run", fake)
    health_waited: list[bool] = []
    monkeypatch.setattr(oracle, "_wait_for_health", lambda start: health_waited.append(True))

    with pytest.raises(pytest.fail.Exception):
        oracle._deploy_stack(time.monotonic(), FRESH_IMAGE_ID)

    assert health_waited == [], "a wrong image must fail before the slow health wait"


def test_compose_keeps_the_image_tag_the_oracle_builds(oracle: ModuleType) -> None:
    """Rule 19 needs no compose change: the file names the tag the build writes."""
    config = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    assert config["services"][oracle.APP_SERVICE]["image"] == oracle.IMAGE_TAG


# ---------------------------------------------------------------------------
# Rule 20: schema by migration, never by create_all
# ---------------------------------------------------------------------------


def _shell_lines(path: Path) -> list[list[str]]:
    """The entrypoint's real commands, as token lists (comments and blanks dropped)."""
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped.split())
    return lines


def test_entrypoint_runs_alembic_upgrade_head_before_serving() -> None:
    commands = _shell_lines(ENTRYPOINT)
    assert ["alembic", "upgrade", "head"] in commands, (
        f"docker-entrypoint.sh must run 'alembic upgrade head'; commands: {commands}"
    )
    migrate_at = commands.index(["alembic", "upgrade", "head"])
    serve_at = next(i for i, c in enumerate(commands) if c[:2] == ["exec", "uvicorn"])
    assert migrate_at < serve_at, "migrations run before uvicorn serves"
    assert ["set", "-e"] in commands[:migrate_at], (
        "set -e must precede the migration so a failed upgrade stops the container "
        "rather than serving on a half-made schema"
    )


def test_smoke_image_uses_that_entrypoint_and_carries_the_migrations() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert 'ENTRYPOINT ["./docker-entrypoint.sh"]' in dockerfile
    assert "COPY alembic/ ./alembic/" in dockerfile
    assert "COPY alembic.ini ./alembic.ini" in dockerfile


def test_smoke_compose_does_not_bypass_the_entrypoint() -> None:
    """No command/entrypoint override on the app service: the image's own
    entrypoint (and so the migration) is what runs."""
    config = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    app = config["services"]["app"]
    assert "command" not in app, "a command: override would skip the entrypoint's migration"
    assert "entrypoint" not in app, "an entrypoint: override would skip the migration"


def _create_all_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "create_all":
            hits.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")
        elif isinstance(node, ast.Name) and node.id == "create_all":
            hits.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")
    return hits


def test_nothing_on_the_smoke_path_calls_create_all() -> None:
    """Nothing under src/ (the served app) nor alembic/env.py (the migration
    runner) creates the schema from the model; the migrations are the schema."""
    offenders: list[str] = []
    for py in sorted(SRC_DIR.rglob("*.py")):
        offenders.extend(_create_all_calls(py))
    offenders.extend(_create_all_calls(ALEMBIC_ENV))
    assert offenders == [], (
        "create_all found on the smoke path; the schema must come from "
        f"'alembic upgrade head' only: {offenders}"
    )
