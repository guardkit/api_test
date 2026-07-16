#!/usr/bin/env python3
"""F4 DCL gate — the `dcl` spec-track's live gate (Phase D / D3).

ONE generic gate script (no per-feature branch): it locates the feature's
DERIVED assertion set under ``qa/dcl/derived/`` and delegates execution to
guardkit's generic ``assertion_runner`` (the same executor ``guardkit dcl run``
drives), which emits the F4 gate envelope. guardkit is importable in the QA
driver env — the ``local_live_gate.py`` precedent for reaching guardkit from an
api_test gate script.

WHICH derived set: the env var ``DCL_FEATURE`` names it explicitly
(``qa/dcl/derived/<DCL_FEATURE>.yaml``); absent, the sole ``*.yaml`` under
``qa/dcl/derived/`` is used. Zero sets, an unknown ``DCL_FEATURE``, or an
ambiguous multi-set directory with no selector -> an honest LOUD failure (the
``feature_behaviour_gate.py`` ``not_instantiated`` precedent), never a vacuous
green.

Base URL comes from the env var NAMED ``API_TEST_BASE_URL`` (LPA-02 — never a
hard-coded URL), matching this gate's registry entry ``base_url_env`` and the
runner's default. The F4 contract: exit 0 = pass; a non-zero exit enumerates the
failing assertions as the JSON results envelope on stdout.

    API_TEST_BASE_URL=http://localhost:8901 python3 qa/gates/dcl_gate.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import List

GATE_ID = "dcl-stats"
BASE_URL_ENV = "API_TEST_BASE_URL"
DERIVED_DIR = Path("qa/dcl/derived")


def _fail(assertion_id: str, observed: str, expected: str) -> None:
    """Emit a single honest failure in the F4 envelope and exit non-zero."""
    print(json.dumps({"assertions": [{
        "id": f"{GATE_ID}::{assertion_id}",
        "status": "fail",
        "observed": observed,
        "expected": expected,
        "evidence_ref": None,
    }]}))
    sys.exit(1)


def _locate_derived_set() -> Path:
    """Resolve the feature's derived assertion set, or fail LOUD."""
    feature = os.environ.get("DCL_FEATURE")
    if feature:
        path = DERIVED_DIR / f"{feature}.yaml"
        if not path.is_file():
            _fail(
                "derived_set_missing",
                f"DCL_FEATURE={feature} -> {path} not found",
                f"a derived assertion set at {path} (run `guardkit dcl derive "
                f"--feature {feature}`)",
            )
        return path

    if not DERIVED_DIR.is_dir():
        _fail(
            "derived_dir_missing",
            f"{DERIVED_DIR} does not exist",
            "the derived assertion set directory (run `guardkit dcl derive`)",
        )
    candidates: List[Path] = sorted(DERIVED_DIR.glob("*.yaml"))
    if not candidates:
        _fail(
            "no_derived_set",
            f"no *.yaml under {DERIVED_DIR}",
            "a derived assertion set (run `guardkit dcl derive --feature <ID>`)",
        )
    if len(candidates) > 1:
        _fail(
            "ambiguous_derived_set",
            f"{len(candidates)} derived sets {[p.name for p in candidates]}",
            "set DCL_FEATURE to name which derived set to run",
        )
    return candidates[0]


def main() -> None:
    # guardkit is importable in the QA driver env (local_live_gate.py precedent).
    try:
        from guardkit.qa.dcl.assertion_runner import RunnerError, run_file
    except ImportError as exc:  # pragma: no cover - environment fault
        _fail(
            "guardkit_import",
            f"could not import guardkit assertion_runner: {exc}",
            "guardkit importable in the QA driver env (run under `uv run --no-sync`)",
        )
        return

    derived_set = _locate_derived_set()
    try:
        envelope, exit_code = run_file(derived_set, BASE_URL_ENV)
    except RunnerError as exc:
        # A config/instrument fault (unreadable set / unset base URL) — LOUD, exit 1.
        _fail("runner_fault", str(exc), f"a runnable derived set + ${BASE_URL_ENV} set")
        return

    print(json.dumps(envelope))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
