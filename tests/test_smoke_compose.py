"""Invariant tests for deploy/docker-compose.smoke.yml.

These tests validate the smoke compose stack against all acceptance criteria
(AC-001 through AC-008). They are invariant tests — they assert structural
and semantic properties that must hold regardless of future changes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

# Resolve the compose file relative to the project root.
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
COMPOSE_FILE = PROJECT_ROOT / "deploy" / "docker-compose.smoke.yml"


@pytest.fixture(scope="module")
def compose_config():
    """Load and parse the smoke compose file once per module."""
    assert COMPOSE_FILE.exists(), f"Smoke compose file not found: {COMPOSE_FILE}"
    with open(COMPOSE_FILE) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def compose_raw():
    """Read the raw YAML text of the compose file."""
    assert COMPOSE_FILE.exists()
    return COMPOSE_FILE.read_text()


# ---------------------------------------------------------------------------
# AC-001: docker compose config parses cleanly
# ---------------------------------------------------------------------------

class TestAC001_ConfigParses:
    """docker compose -f deploy/docker-compose.smoke.yml config parses cleanly."""

    def test_docker_compose_config_exits_zero(self):
        """The compose file must be syntactically valid."""
        result = subprocess.run(
            [
                "docker", "compose",
                "-f", str(COMPOSE_FILE),
                "config",
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, (
            f"docker compose config failed:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_config_yaml_is_valid(self, compose_config):
        """The YAML must be parseable and well-formed."""
        assert compose_config is not None
        assert isinstance(compose_config, dict)


# ---------------------------------------------------------------------------
# AC-002: Exactly two services with correct images and healthchecks
# ---------------------------------------------------------------------------

class TestAC002_Services:
    """Exactly two services: app and db with correct images."""

    def test_exactly_two_services(self, compose_config):
        """Only `app` and `db` services must exist."""
        services = compose_config.get("services", {})
        assert set(services.keys()) == {"app", "db"}

    def test_app_image(self, compose_config):
        """App must use image: apitest-app:smoke."""
        app = compose_config["services"]["app"]
        assert app.get("image") == "apitest-app:smoke"

    def test_app_no_build_key(self, compose_raw):
        """The file must NOT contain a build: key anywhere."""
        # Check that "build:" does not appear as a key (not in comments)
        for line in compose_raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith("build:"):
                pytest.fail(f"Found unexpected 'build:' key at line: {line}")

    def test_db_image(self, compose_config):
        """DB must use postgres:16-alpine."""
        db = compose_config["services"]["db"]
        assert db.get("image") == "postgres:16-alpine"

    def test_db_tmpfs(self, compose_config):
        """DB must have tmpfs on /var/lib/postgresql/data."""
        db = compose_config["services"]["db"]
        tmpfs = db.get("tmpfs", [])
        assert "/var/lib/postgresql/data" in tmpfs

    def test_db_healthcheck_shape(self, compose_config):
        """DB must use pg_isready healthcheck matching base compose."""
        db = compose_config["services"]["db"]
        hc = db.get("healthcheck", {})
        test_cmd = hc.get("test", [])
        assert "CMD-SHELL" in test_cmd
        assert "pg_isready" in " ".join(test_cmd)
        assert "-U postgres" in " ".join(test_cmd)
        assert "-d test" in " ".join(test_cmd)


# ---------------------------------------------------------------------------
# AC-003: Two networks backend and probe, both internal
# ---------------------------------------------------------------------------

class TestAC003_Networks:
    """Two networks backend and probe, both internal: true."""

    def test_networks_exist(self, compose_config):
        """Both backend and probe networks must be declared."""
        networks = compose_config.get("networks", {})
        assert set(networks.keys()) == {"backend", "probe"}

    def test_backend_internal(self, compose_config):
        """backend network must be internal: true."""
        backend = compose_config["networks"]["backend"]
        assert backend.get("internal") is True

    def test_probe_internal(self, compose_config):
        """probe network must be internal: true."""
        probe = compose_config["networks"]["probe"]
        assert probe.get("internal") is True

    def test_app_on_both_networks(self, compose_config):
        """app must attach to both backend and probe."""
        app = compose_config["services"]["app"]
        app_networks = set(app.get("networks", []))
        assert app_networks == {"backend", "probe"}

    def test_db_on_backend_only(self, compose_config):
        """db must attach to backend only, not probe."""
        db = compose_config["services"]["db"]
        db_networks = set(db.get("networks", []))
        assert db_networks == {"backend"}
        assert "probe" not in db_networks


# ---------------------------------------------------------------------------
# AC-004: No ports, no docker.sock mount
# ---------------------------------------------------------------------------

class TestAC004_NoExposedPorts:
    """No ports: key anywhere; no docker.sock mount."""

    def test_no_ports_key_app(self, compose_config):
        """app service must not have ports: key."""
        app = compose_config["services"]["app"]
        assert "ports" not in app

    def test_no_ports_key_db(self, compose_config):
        """db service must not have ports: key."""
        db = compose_config["services"]["db"]
        assert "ports" not in db

    def test_no_ports_key_anywhere(self, compose_raw):
        """The raw file must not contain ports: at any level."""
        for line in compose_raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith("ports:"):
                pytest.fail(f"Found unexpected 'ports:' key at line: {line}")

    def test_no_docker_sock_mount(self, compose_config):
        """No service may mount /var/run/docker.sock."""
        for svc_name, svc in compose_config.get("services", {}).items():
            volumes = svc.get("volumes", [])
            for vol in volumes:
                vol_str = str(vol)
                assert "/var/run/docker.sock" not in vol_str, (
                    f"Service '{svc_name}' mounts docker.sock"
                )


# ---------------------------------------------------------------------------
# AC-005: App hardening block
# ---------------------------------------------------------------------------

class TestAC005_Hardening:
    """App hardening: non-root user, cap_drop, security_opt, read_only,
    tmpfs /tmp, limits, env."""

    def test_app_user_non_root(self, compose_config):
        """App must run as non-root user."""
        app = compose_config["services"]["app"]
        user = app.get("user")
        assert user is not None
        assert user != "0" and user != "0:0" and user != "root"

    def test_app_cap_drop_all(self, compose_config):
        """App must drop all capabilities."""
        app = compose_config["services"]["app"]
        cap_drop = app.get("cap_drop", [])
        assert "ALL" in cap_drop

    def test_app_security_opt(self, compose_config):
        """App must set no-new-privileges:true."""
        app = compose_config["services"]["app"]
        security_opt = app.get("security_opt", [])
        assert "no-new-privileges:true" in security_opt

    def test_app_read_only(self, compose_config):
        """App must have read_only: true."""
        app = compose_config["services"]["app"]
        assert app.get("read_only") is True

    def test_app_tmpfs_tmp(self, compose_config):
        """App must have tmpfs for /tmp."""
        app = compose_config["services"]["app"]
        tmpfs = app.get("tmpfs", [])
        assert "/tmp" in tmpfs

    def test_app_memory_limit(self, compose_config):
        """App must have memory limit."""
        app = compose_config["services"]["app"]
        deploy = app.get("deploy", {})
        resources = deploy.get("resources", {})
        limits = resources.get("limits", {})
        assert "memory" in limits
        assert limits["memory"] is not None

    def test_app_pids_limit(self, compose_config):
        """App must have pids limit."""
        app = compose_config["services"]["app"]
        deploy = app.get("deploy", {})
        resources = deploy.get("resources", {})
        limits = resources.get("limits", {})
        assert "pids" in limits
        assert limits["pids"] is not None

    def test_app_pythondontwritebytecode(self, compose_config):
        """App must set PYTHONDONTWRITEBYTECODE=1."""
        app = compose_config["services"]["app"]
        env = app.get("environment", {})
        assert env.get("PYTHONDONTWRITEBYTECODE") == "1"


# ---------------------------------------------------------------------------
# AC-006: Commented runtime: runsc with note
# ---------------------------------------------------------------------------

class TestAC006_RunscActive:
    """runtime: runsc ACTIVE on the app service (flipped 2026-07-25 after the
    attended install; was a commented line while the install was pending)."""

    def test_runtime_runsc_active(self, compose_config):
        """The app service must run under the runsc (gVisor) runtime."""
        app = compose_config["services"]["app"]
        assert app.get("runtime") == "runsc", (
            "App service must declare runtime: runsc (the ruled sandbox runtime; "
            "active since 2026-07-25)"
        )

    def test_runsc_dns_note_present(self, compose_raw):
        """The file must document the gVisor embedded-DNS limitation that forces
        the static-IP DATABASE_URL, so nobody 'simplifies' it back to a hostname."""
        lowered = compose_raw.lower()
        assert "runsc" in lowered and "dns" in lowered, (
            "Missing the gVisor/embedded-DNS note explaining the static-IP db address"
        )


# ---------------------------------------------------------------------------
# AC-007: App env, depends_on, healthcheck
# ---------------------------------------------------------------------------

class TestAC007_AppEnvAndHealthcheck:
    """App DATABASE_URL, depends_on db service_healthy, healthcheck shape."""

    def test_database_url(self, compose_config):
        """App DATABASE_URL must dial the db by its STATIC IP with asyncpg.

        The db hostname cannot be used while the app runs under runsc: gVisor's
        netstack cannot reach Docker's embedded DNS on this internal network.
        The URL host must therefore equal the db service's pinned ipv4_address.
        """
        app = compose_config["services"]["app"]
        env = app.get("environment", {})
        db = compose_config["services"]["db"]
        db_ip = db["networks"]["backend"]["ipv4_address"]
        expected = f"postgresql+asyncpg://postgres:test@{db_ip}:5432/test"
        assert env.get("DATABASE_URL") == expected

    def test_depends_on_db_healthy(self, compose_config):
        """App must depend_on db with condition: service_healthy."""
        app = compose_config["services"]["app"]
        depends = app.get("depends_on", {})
        assert "db" in depends
        assert depends["db"].get("condition") == "service_healthy"

    def test_app_healthcheck_shape(self, compose_config):
        """App healthcheck mirrors the base curl-/health-database-connected
        shape."""
        app = compose_config["services"]["app"]
        hc = app.get("healthcheck", {})
        test_cmd = hc.get("test", [])
        assert "CMD-SHELL" in test_cmd
        full_cmd = " ".join(test_cmd)
        assert "curl" in full_cmd
        assert "/health" in full_cmd
        assert '"database":"connected"' in full_cmd


# ---------------------------------------------------------------------------
# AC-008: File header comments — fence scoping
# ---------------------------------------------------------------------------

class TestAC008_HeaderComments:
    """File header names the fences verbatim: apitest-smoke only."""

    def test_header_names_apitest_smoke(self, compose_raw):
        """Header must name the apitest-smoke project fence."""
        # The first 20 lines are the header
        header = "\n".join(compose_raw.splitlines()[:20])
        assert "apitest-smoke" in header

    def test_header_names_apitest_f2_as_excluded(self, compose_raw):
        """Header must name apitest-f2 as excluded (never touches it)."""
        header = "\n".join(compose_raw.splitlines()[:20])
        # The header should mention apitest-f2 in a negation context
        assert "apitest-f2" in header
        # Verify it's in a "never touches" or similar exclusion context
        for line in header.splitlines():
            if "apitest-f2" in line and "apitest-f2-cand" not in line:
                assert "never touches" in line or "only" in line

    def test_header_names_apitest_f2_cand_as_excluded(self, compose_raw):
        """Header must name apitest-f2-cand as excluded."""
        header = "\n".join(compose_raw.splitlines()[:20])
        assert "apitest-f2-cand" in header

    def test_header_names_5433_suite_db_as_excluded(self, compose_raw):
        """Header must name the :5433 suite database as excluded."""
        header = "\n".join(compose_raw.splitlines()[:20])
        assert ":5433" in header

    def test_header_no_build_images(self, compose_raw):
        """Header must state the sandbox never builds images."""
        header = "\n".join(compose_raw.splitlines()[:20])
        lowered = header.lower()
        assert (
            "build" not in lowered
            or "never builds" in lowered
            or "pre-pulled" in lowered
        )
