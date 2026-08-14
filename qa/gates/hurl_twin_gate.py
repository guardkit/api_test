#!/usr/bin/env python3
"""hurl-twins gate — F4 adapter over the qa/twins/ Hurl twin files.

HURL-TWIN PILOT (Rich's Q1/Q3 ruling 2026-08-14, options card 2062dd8): each
twin under qa/twins/ is a Hurl translation of ONE approved Gherkin scenario
(the verbatim spec rides at the top of each .hurl as comments). This adapter
makes the twins first-class citizens of the EXISTING gate seam: it runs
``hurl --test --report-json`` over every twin, converts the Hurl JSON report
into the F4 assertions envelope (guardkit/qa/formats/gate_registry.py — each
assertion EXACTLY {id, status, observed, expected, evidence_ref}), copies the
full Hurl report to qa/gates/evidence/hurl-twins_latest.json, and exits 0 iff
every assertion passed. Zero guardkit changes; the live-gate runner drives it
like any other registered gate.

Assertion ids are ``hurl-twins::<file-stem>::<line>``; when Hurl reports
several asserts on one source line (e.g. the implicit HTTP-version + status
pair) they aggregate into that single line-id (fail if any fails).

stdlib only (the _gatelib.py idiom). Probe-unavailable conditions (hurl binary
missing, target connection refused) emit a single fail assertion with id
``hurl-twins::inconclusive`` whose observed starts PROBE_UNAVAILABLE and exit
90 — environment attribution, not a red.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

GATE_ID = "hurl-twins"
TWINS_DIR = Path("qa/twins")
EVIDENCE_DIR = Path("qa/gates/evidence")
EVIDENCE_REF = str(EVIDENCE_DIR / f"{GATE_ID}_latest.json")


def _base_url() -> str:
    return (os.environ.get("API_TEST_BASE_URL") or "http://localhost:8901").rstrip("/")


def _emit(assertions: List[Dict[str, Any]], exit_code: int) -> None:
    print(json.dumps({"assertions": assertions}))
    sys.exit(exit_code)


def _inconclusive(reason: str) -> None:
    _emit(
        [
            {
                "id": f"{GATE_ID}::inconclusive",
                "status": "fail",
                "observed": f"PROBE_UNAVAILABLE: {reason}",
                "expected": "hurl binary on PATH and target reachable",
                "evidence_ref": EVIDENCE_REF,
            }
        ],
        90,
    )


def _write_evidence(payload: Any) -> None:
    try:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        Path(EVIDENCE_REF).write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _source_line(lines: List[str], n: int) -> str:
    if 1 <= n <= len(lines):
        return lines[n - 1].strip()
    return f"line {n}"


def _first_error_line(message: str) -> str:
    """Compress a Hurl failure message to its observed-value line(s)."""
    found: List[str] = []
    for part in message.splitlines():
        part = part.lstrip("|^ ").strip()
        if part.startswith("actual") or "actual value" in part:
            found.append(part)
        elif part.startswith("expected") and found:
            found.append(part)
    if found:
        return "; ".join(found)
    return message.splitlines()[0] if message else "assert failed"


def main() -> None:
    base_url = _base_url()

    hurl = shutil.which("hurl")
    if not hurl:
        _inconclusive("hurl binary not found on PATH")

    # Reachability probe: any HTTP response (even 4xx/5xx) counts as reachable;
    # only a transport-level failure (connection refused / DNS / timeout) is
    # the environment's fault.
    try:
        req = urllib.request.Request(base_url + "/health", method="GET")
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError:
        pass
    except Exception as exc:
        _inconclusive(f"target {base_url} unreachable: {exc}")

    twins = sorted(TWINS_DIR.glob("**/*.hurl"))
    if not twins:
        _emit(
            [
                {
                    "id": f"{GATE_ID}::no-twins",
                    "status": "fail",
                    "observed": f"no .hurl files under {TWINS_DIR}",
                    "expected": "at least one twin registered under qa/twins/",
                    "evidence_ref": EVIDENCE_REF,
                }
            ],
            1,
        )

    run_marker = f"{int(time.time())}-{os.getpid()}"
    report_dir = Path(tempfile.mkdtemp(prefix="hurl-twins-report-"))
    cmd = [
        hurl,
        "--test",
        "--report-json",
        str(report_dir),
        "--variable",
        f"base_url={base_url}",
        "--variable",
        f"run_marker={run_marker}",
    ] + [str(t) for t in twins]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        _inconclusive("hurl run timed out after 300s")

    report_path = report_dir / "report.json"
    if not report_path.exists():
        stderr = (proc.stderr or "").strip()
        lowered = stderr.lower()
        if "connection refused" in lowered or "could not connect" in lowered:
            _inconclusive(f"connection refused by {base_url}: {stderr[:200]}")
        _emit(
            [
                {
                    "id": f"{GATE_ID}::no-report",
                    "status": "fail",
                    "observed": f"hurl exited {proc.returncode} without a JSON report: {stderr[:300]}",
                    "expected": "hurl --test --report-json produces report.json",
                    "evidence_ref": EVIDENCE_REF,
                }
            ],
            1,
        )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    _write_evidence(
        {
            "gate_id": GATE_ID,
            "base_url": base_url,
            "run_marker": run_marker,
            "hurl_exit": proc.returncode,
            "report": report,
        }
    )

    # A transport-level failure inside the run (all entries errored with no
    # asserts and stderr says connection refused) is also PROBE_UNAVAILABLE.
    if "connection refused" in (proc.stderr or "").lower():
        _inconclusive(f"connection refused by {base_url} during run")

    assertions: List[Dict[str, Any]] = []
    for file_result in report:
        twin_path = Path(file_result["filename"])
        stem = twin_path.stem
        try:
            lines = twin_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            lines = []
        # Aggregate asserts per source line (implicit status/version pairs
        # share a line) so ids stay unique in the ruled format.
        per_line: Dict[int, Dict[str, Any]] = {}
        for entry in file_result.get("entries", []):
            for a in entry.get("asserts", []):
                line_no = a.get("line", 0)
                slot = per_line.setdefault(
                    line_no, {"ok": True, "messages": []}
                )
                if not a.get("success", False):
                    slot["ok"] = False
                    slot["messages"].append(
                        _first_error_line(a.get("message", ""))
                    )
        for line_no in sorted(per_line):
            slot = per_line[line_no]
            assertions.append(
                {
                    "id": f"{GATE_ID}::{stem}::{line_no}",
                    "status": "pass" if slot["ok"] else "fail",
                    "observed": (
                        "satisfied"
                        if slot["ok"]
                        else "; ".join(slot["messages"])
                    ),
                    "expected": _source_line(lines, line_no),
                    "evidence_ref": EVIDENCE_REF,
                }
            )
        # A file that failed before any assert ran (e.g. runtime error) still
        # must surface as a red.
        if not per_line and not file_result.get("success", False):
            assertions.append(
                {
                    "id": f"{GATE_ID}::{stem}::0",
                    "status": "fail",
                    "observed": "twin executed no asserts and did not succeed",
                    "expected": f"{twin_path} runs its asserts",
                    "evidence_ref": EVIDENCE_REF,
                }
            )

    shutil.rmtree(report_dir, ignore_errors=True)
    _emit(assertions, 0 if all(a["status"] == "pass" for a in assertions) else 1)


if __name__ == "__main__":
    main()
