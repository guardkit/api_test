#!/usr/bin/env python3
"""Small helpers for qa/feature-check.sh — reading the feature record, finding
each scenario's frozen Hurl twin, and two odds and ends the shell cannot do
safely (pick a free port, wait for a URL, print one line of JSON).

This file knows NOTHING about any particular endpoint. It reads whatever
feature record the factory hands it and answers three questions per scenario:
what is it called, who verifies it, and which twin file proves it.

THE TWIN RULE IS NOT INVENTED HERE. It is a faithful copy of the rule guardkit
already enforces at build completion (guardkit/orchestrator/twin_coverage.py,
2026-08-26): a scenario stamped ``verifier: hurl`` is covered when EITHER its
stamp names an existing ``.hurl`` file (``test_ref``), OR some ``.hurl`` file
under ``qa/twins/`` carries a comment line reading ``Scenario: <the title>``.
Matching is exact; only trailing decoration set off by whitespace and starting
``(``, ``-`` or ``=`` is tolerated, so a longer title never satisfies a shorter
stamp. If that rule ever changes upstream, change it here too — the whole point
is that this check and the build-completion check agree about what evidence is.

Usage (all output is plain text, one record per line):

    feature_check_twins.py scenarios <record.yaml> <worktree-root>
        One TAB-separated line per scenario:
            hurl-twin    <title>  <verifier>  <twin path, repo-relative>
            hurl-missing <title>  <verifier>  -
            other        <title>  <verifier>  -
        Exit 0 when the record parsed and named at least one scenario;
        exit 3 (with a plain reason on stderr) when it did not.

    feature_check_twins.py freeport
        A free TCP port on 127.0.0.1.

    feature_check_twins.py wait-health <url> <seconds>
        Exit 0 as soon as the URL answers 200, exit 1 when the time runs out.

    feature_check_twins.py json-line <file of titles, one per line>
        The one coverage line guardkit reads out of this check's stdout.
"""

from __future__ import annotations

import json
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TWINS_RELATIVE_DIR = Path("qa") / "twins"

# Copied from guardkit's twin_coverage: longest keyword first so
# "Scenario Outline:" never half-matches as "Scenario:".
_TWIN_TITLE_RE = re.compile(
    r"(?:Scenario Outline|Scenario Template|Scenario|Example)\s*:\s*(?P<rest>\S.*?)\s*$"
)


def _fail(message: str) -> "NoReturn":  # type: ignore[valid-type]
    print(message, file=sys.stderr)
    raise SystemExit(3)


def _extract_twin_titles(text: str) -> List[str]:
    """Title candidates from one twin file's COMMENT lines only."""
    candidates: List[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            continue
        match = _TWIN_TITLE_RE.search(stripped)
        if match:
            candidates.append(match.group("rest"))
    return candidates


def _candidate_matches_title(candidate: str, title: str) -> bool:
    """Exact title match, tolerating only set-off trailing decoration."""
    if candidate == title:
        return True
    if candidate.startswith(title):
        rest = candidate[len(title):]
        if rest[:1] in (" ", "\t"):
            return rest.strip().startswith(("(", "-", "="))
    return False


def _stamp_field(stamp: Any, name: str) -> Any:
    if isinstance(stamp, dict):
        return stamp.get(name)
    return getattr(stamp, name, None)


def _scenario_items(data: Any) -> List[Tuple[str, Any]]:
    """The record's scenarios as (title, stamp) pairs.

    A mapping of title -> stamp is the shape the factory writes. A list of
    rows carrying their own title is accepted too, because a record that is
    readable should not fail on its shape.
    """
    scenarios = data.get("scenarios") if isinstance(data, dict) else None
    items: List[Tuple[str, Any]] = []
    if isinstance(scenarios, dict):
        for title, stamp in scenarios.items():
            items.append((str(title), stamp))
    elif isinstance(scenarios, list):
        for row in scenarios:
            if not isinstance(row, dict):
                continue
            title = None
            for key in ("title", "scenario", "name", "text"):
                value = row.get(key)
                if isinstance(value, str) and value.strip():
                    title = value.strip()
                    break
            if title:
                items.append((title, row))
    return items


def cmd_scenarios(record_path: str, root_path: str) -> int:
    try:
        import yaml
    except Exception as exc:  # noqa: BLE001
        _fail(f"feature-check: no YAML reader available to read the record ({exc})")

    root = Path(root_path).resolve()
    record = Path(record_path)
    if not record.is_absolute():
        record = root / record
    if not record.is_file():
        _fail(
            "feature-check: the feature record was not readable at "
            f"{record} — GUARDKIT_FEATURE_RECORD must name the feature's "
            "YAML file."
        )
    try:
        data = yaml.safe_load(record.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _fail(f"feature-check: the feature record {record} could not be read: {exc}")
    if not isinstance(data, dict):
        _fail(
            f"feature-check: the feature record {record} is not a mapping, so "
            "it names no scenarios."
        )

    items = _scenario_items(data)
    if not items:
        _fail(
            f"feature-check: the feature record {record} names no scenarios, "
            "so there is nothing this check could prove. A feature with no "
            "scenarios cannot pass."
        )

    # Scan qa/twins/ once: path -> the titles its comments claim.
    twins_dir = root / TWINS_RELATIVE_DIR
    twin_titles: List[Tuple[str, List[str]]] = []
    if twins_dir.is_dir():
        for path in sorted(twins_dir.rglob("*.hurl")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            twin_titles.append((str(path.relative_to(root)), _extract_twin_titles(text)))

    for title, stamp in items:
        verifier = _stamp_field(stamp, "verifier")
        verifier_text = str(verifier) if isinstance(verifier, str) and verifier.strip() else "-"
        if verifier_text != "hurl":
            print(f"other\t{title}\t{verifier_text}\t-")
            continue

        twin: Optional[str] = None
        test_ref = _stamp_field(stamp, "test_ref")
        if (
            isinstance(test_ref, str)
            and test_ref.strip().endswith(".hurl")
            and (root / test_ref.strip()).is_file()
        ):
            twin = test_ref.strip()
        else:
            for rel_path, candidates in twin_titles:
                if any(_candidate_matches_title(c, title) for c in candidates):
                    twin = rel_path
                    break

        if twin is None:
            print(f"hurl-missing\t{title}\t{verifier_text}\t-")
        else:
            print(f"hurl-twin\t{title}\t{verifier_text}\t{twin}")
    return 0


def cmd_freeport() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        print(sock.getsockname()[1])
    finally:
        sock.close()
    return 0


def cmd_wait_health(url: str, seconds: str) -> int:
    deadline = time.monotonic() + float(seconds)
    last = "no answer yet"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return 0
                last = f"HTTP {response.status}"
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001 — still starting up
            last = str(exc)
        time.sleep(0.5)
    print(f"feature-check: {url} never became healthy ({last})", file=sys.stderr)
    return 1


def cmd_json_line(titles_file: str) -> int:
    titles: List[str] = []
    path = Path(titles_file)
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and line not in titles:
                titles.append(line)
    payload: Dict[str, Any] = {"guardkit_feature_check": {"scenarios_covered": titles}}
    print(json.dumps(payload))
    return 0


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        _fail("feature-check: feature_check_twins.py needs a mode")
    mode = argv[1]
    if mode == "scenarios" and len(argv) == 4:
        return cmd_scenarios(argv[2], argv[3])
    if mode == "freeport":
        return cmd_freeport()
    if mode == "wait-health" and len(argv) == 4:
        return cmd_wait_health(argv[2], argv[3])
    if mode == "json-line" and len(argv) == 3:
        return cmd_json_line(argv[2])
    _fail(f"feature-check: feature_check_twins.py does not understand {' '.join(argv[1:])!r}")
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
