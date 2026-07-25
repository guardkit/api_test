"""Hermetic unit tests for the smoke probe (TASK-SMOKE-002).

No Docker, no network -- all tests use in-process logic or monkeypatching.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROBE_PATH = Path(__file__).resolve().parent.parent / "qa" / "smoke" / "probe.py"


# ---------------------------------------------------------------------------
# AC-002: stdlib-only import rule (AST walk)
# ---------------------------------------------------------------------------


def _stdlib_modules() -> set[str]:
    """Return the set of known stdlib top-level module names."""
    return {
        "__future__",
        "abc",
        "argparse",
        "array",
        "ast",
        "asyncio",
        "atexit",
        "base64",
        "binascii",
        "bisect",
        "builtins",
        "bz2",
        "calendar",
        "cgi",
        "cmath",
        "cmd",
        "codecs",
        "collections",
        "concurrent",
        "configparser",
        "contextlib",
        "contextvars",
        "copy",
        "csv",
        "ctypes",
        "curses",
        "dataclasses",
        "datetime",
        "dbm",
        "decimal",
        "difflib",
        "dis",
        "distutils",
        "doctest",
        "email",
        "encodings",
        "enum",
        "errno",
        "faulthandler",
        "fcntl",
        "filecmp",
        "fileinput",
        "fnmatch",
        "fractions",
        "ftplib",
        "functools",
        "gc",
        "getopt",
        "getpass",
        "gettext",
        "glob",
        "grp",
        "gzip",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "imaplib",
        "importlib",
        "inspect",
        "io",
        "ipaddress",
        "itertools",
        "json",
        "keyword",
        "linecache",
        "locale",
        "logging",
        "lzma",
        "mailbox",
        "marshal",
        "math",
        "mimetypes",
        "mmap",
        "multiprocessing",
        "netrc",
        "numbers",
        "operator",
        "optparse",
        "os",
        "pathlib",
        "pdb",
        "pickle",
        "pipes",
        "pkgutil",
        "platform",
        "plistlib",
        "poplib",
        "posix",
        "posixpath",
        "pprint",
        "profile",
        "pstats",
        "pty",
        "pwd",
        "py_compile",
        "queue",
        "quopri",
        "random",
        "re",
        "readline",
        "reprlib",
        "resource",
        "runpy",
        "sched",
        "secrets",
        "select",
        "selectors",
        "shelve",
        "shlex",
        "shutil",
        "signal",
        "site",
        "smtplib",
        "socket",
        "socketserver",
        "sqlite3",
        "ssl",
        "stat",
        "statistics",
        "string",
        "struct",
        "subprocess",
        "symtable",
        "sys",
        "sysconfig",
        "syslog",
        "tabnanny",
        "tarfile",
        "tempfile",
        "termios",
        "test",
        "textwrap",
        "threading",
        "time",
        "timeit",
        "token",
        "tokenize",
        "tomllib",
        "trace",
        "traceback",
        "tracemalloc",
        "tty",
        "turtle",
        "types",
        "typing",
        "unicodedata",
        "unittest",
        "urllib",
        "uuid",
        "venv",
        "warnings",
        "wave",
        "weakref",
        "webbrowser",
        "wsgiref",
        "xml",
        "xmlrpc",
        "zipapp",
        "zipfile",
        "zipimport",
        "zlib",
        "_thread",
    }


def test_probe_imports_are_stdlib_only() -> None:
    """Walk probe.py's AST and assert every top-level import is stdlib."""
    source = _PROBE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_PROBE_PATH))

    stdlib = _stdlib_modules()
    imported: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                imported.append(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                top = node.module.split(".")[0]
                imported.append(top)

    non_stdlib = [mod for mod in imported if mod not in stdlib]
    assert not non_stdlib, (
        f"Non-stdlib imports found: {non_stdlib}. "
        "probe.py must only use Python standard-library modules."
    )


# ---------------------------------------------------------------------------
# AC-004: verdict JSON shape
# ---------------------------------------------------------------------------


def test_verdict_json_shape_all_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verdict JSON has correct shape when all checks pass."""
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:9999")
    monkeypatch.setenv("MARKER", "testmarker")
    from qa.smoke.probe import verdict_json  # noqa: E402

    checks = [
        {"id": "check_a", "pass": True, "detail": "ok"},
        {"id": "check_b", "pass": True, "detail": "ok"},
    ]
    result = verdict_json(checks)
    parsed = json.loads(result)
    assert set(parsed.keys()) == {"pass", "marker", "checks"}
    assert parsed["pass"] is True
    assert parsed["marker"] == "testmarker"
    assert isinstance(parsed["checks"], list)
    assert all({"id", "pass", "detail"} <= set(c.keys()) for c in parsed["checks"])


def test_verdict_json_shape_any_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verdict JSON has correct shape with any-fail."""
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:9999")
    monkeypatch.setenv("MARKER", "testmarker")
    from qa.smoke.probe import verdict_json  # noqa: E402

    checks = [
        {"id": "check_a", "pass": True, "detail": "ok"},
        {"id": "check_b", "pass": False, "detail": "failed"},
        {"id": "check_c", "pass": True, "detail": "ok"},
    ]

    result = verdict_json(checks)
    parsed = json.loads(result)
    assert parsed["pass"] is False
    assert len(parsed["checks"]) == 3


# ---------------------------------------------------------------------------
# AC-005: check-aggregation logic
# ---------------------------------------------------------------------------


def test_aggregation_all_pass_yields_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """All-pass -> pass is true."""
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:9999")
    monkeypatch.setenv("MARKER", "testmarker")
    from qa.smoke.probe import verdict_json  # noqa: E402

    checks = [{"id": f"check_{i}", "pass": True, "detail": "ok"} for i in range(5)]
    parsed = json.loads(verdict_json(checks))
    assert parsed["pass"] is True


def test_aggregation_any_fail_yields_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any-fail -> pass is false."""
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:9999")
    monkeypatch.setenv("MARKER", "testmarker")
    from qa.smoke.probe import verdict_json  # noqa: E402

    checks = [
        {"id": "check_0", "pass": True, "detail": "ok"},
        {"id": "check_1", "pass": False, "detail": "boom"},
        {"id": "check_2", "pass": True, "detail": "ok"},
        {"id": "check_3", "pass": True, "detail": "ok"},
        {"id": "check_4", "pass": True, "detail": "ok"},
    ]
    parsed = json.loads(verdict_json(checks))
    assert parsed["pass"] is False


def test_aggregation_all_fail_yields_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """All-fail -> pass is false."""
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:9999")
    monkeypatch.setenv("MARKER", "testmarker")
    from qa.smoke.probe import verdict_json  # noqa: E402

    checks = [{"id": f"check_{i}", "pass": False, "detail": "boom"} for i in range(5)]
    parsed = json.loads(verdict_json(checks))
    assert parsed["pass"] is False


def test_aggregation_empty_checks_yields_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty checks list -> pass is true (vacuously)."""
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:9999")
    monkeypatch.setenv("MARKER", "testmarker")
    from qa.smoke.probe import verdict_json  # noqa: E402

    parsed = json.loads(verdict_json([]))
    assert parsed["pass"] is True


# ---------------------------------------------------------------------------
# AC-004 (seam): single JSON line output with contract keys
# ---------------------------------------------------------------------------


@pytest.mark.seam
def test_probe_verdict_json_is_single_parseable_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify probe.py emits exactly one stdout line of contract-shaped JSON.

    Contract: {"pass": bool, "marker": str,
               "checks": [{"id", "pass", "detail"}...]}
    Producer: TASK-SMOKE-002 (qa/smoke/probe.py)
    Consumer: TASK-SMOKE-003 (tests/acceptance/users_roundtrip.py)
    """
    result = subprocess.run(
        [sys.executable, str(_PROBE_PATH)],
        env={"APP_BASE_URL": "http://127.0.0.1:1", "MARKER": "seamtest"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one stdout line, got {len(lines)}"
    verdict = json.loads(lines[0])
    assert set(verdict) == {"pass", "marker", "checks"}
    assert verdict["pass"] is False and verdict["marker"] == "seamtest"
    assert all({"id", "pass", "detail"} <= set(c) for c in verdict["checks"])
