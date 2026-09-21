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
                                     [<not-checked TSV>] [<observations JSON>]
        The one line guardkit reads out of this check's stdout. Besides the
        scenarios whose twins passed it may carry, since 2026-09-21:
          * not_checked — one {name, reason} per example nothing looked at,
            read from a TAB-separated file of `name<TAB>reason` lines;
          * observations — one {asked, answered} per question this check put
            to the running product, read from the JSON `observe` wrote.
        Central code carries both as text and judges neither.

    feature_check_twins.py could-not-run <reason>
        The same line saying, in so many words, that this check COULD NOT RUN
        (no container runtime, no interpreter, no runner for the twins). That
        is neither a pass nor a fault of the build, and guardkit records it as
        its own third outcome.

    feature_check_twins.py entry-point <worktree-root>
        One line of JSON naming this feature's own entry point, taken from the
        per-feature live-check file THIS BRANCH added under qa/gates/ (its SPEC
        block's request method and path), found from what the branch changed
        against its base, or failing that from qa/gates/registry.yaml. Prints
        {"found": false, "reason": "..."} when there is no such file or more
        than one: nothing is guessed.

    feature_check_twins.py observe <base-url> <entry-point JSON file>
        Ask the entry point above on the empty database, create a few records
        through the product's OWN published interface, ask it again, and print
        each as {"asked", "answered"}. It compares nothing and decides nothing:
        the words go on the merge card so a person can read what happened.

    feature_check_twins.py table <tab-separated file>
        The results table, columns aligned by CHARACTER count, nothing cut.

    feature_check_twins.py report-requests <hurl report.json>
        How many requests that hurl run actually sent, counted from hurl's
        own machine-readable report (--report-json). Prints -1 when the
        report is missing or unreadable, so the caller can say so plainly
        instead of guessing. A twin that sent 0 requests proved nothing,
        whatever it exited with.
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


def _read_not_checked_tsv(path_text: Optional[str]) -> List[Dict[str, str]]:
    """`name<TAB>reason` lines as the {name, reason} entries guardkit carries."""
    entries: List[Dict[str, str]] = []
    if not path_text:
        return entries
    path = Path(path_text)
    if not path.is_file():
        return entries
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        name, _, reason = line.partition("\t")
        name = name.strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        entries.append({"name": name, "reason": reason.strip()})
    return entries


def _read_observations_json(path_text: Optional[str]) -> List[Dict[str, str]]:
    """The {asked, answered} pairs `observe` wrote, or nothing at all."""
    if not path_text:
        return []
    path = Path(path_text)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — unreadable observations are simply absent
        return []
    raw = data.get("observations") if isinstance(data, dict) else data
    out: List[Dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and ("asked" in item or "answered" in item):
                out.append(
                    {
                        "asked": str(item.get("asked") or ""),
                        "answered": str(item.get("answered") or ""),
                    }
                )
    return out


def cmd_json_line(
    titles_file: str,
    not_checked_file: Optional[str] = None,
    observations_file: Optional[str] = None,
) -> int:
    titles: List[str] = []
    path = Path(titles_file)
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and line not in titles:
                titles.append(line)
    block: Dict[str, Any] = {"scenarios_covered": titles}

    not_checked = _read_not_checked_tsv(not_checked_file)
    if not_checked:
        block["not_checked"] = not_checked
    observations = _read_observations_json(observations_file)
    if observations:
        block["observations"] = observations

    # An example nothing looked at is never also claimed as covered. The
    # factory removes such a name itself; this check does not hand it one.
    blocked = {e["name"].strip().lower() for e in not_checked}
    if blocked:
        block["scenarios_covered"] = [
            t for t in titles if t.strip().lower() not in blocked
        ]

    print(json.dumps({"guardkit_feature_check": block}))
    return 0


def cmd_could_not_run(reason: str) -> int:
    """Say in so many words that this check could not run, and why."""
    text = " ".join((reason or "").split()) or "no reason was given"
    print(json.dumps({"guardkit_feature_check": {"could_not_run": text}}))
    return 0


def cmd_report_requests(report_path: str) -> int:
    """Print how many requests hurl actually sent, from hurl's own report.

    hurl 8.0.1's ``--report-json <dir>`` writes ``<dir>/report.json``: a list
    with one object per .hurl file, each carrying an ``entries`` list — one
    entry per request the run actually executed. An empty ``entries`` list
    means nothing was sent: a file of comments, or a file whose requests were
    never reached. -1 means the report could not be read at all.
    """
    path = Path(report_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — unreadable is its own answer
        print(-1)
        return 0
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        print(-1)
        return 0
    total = 0
    for row in data:
        if not isinstance(row, dict):
            continue
        entries = row.get("entries")
        if isinstance(entries, list):
            total += len(entries)
    print(total)
    return 0


# ---------------------------------------------------------------------------
# 2026-09-21: the feature's own entry point, and what it answers.
#
# This check used to stop dead when a scenario had no twin, so it started
# nothing and the merge card carried no evidence at all. It now always starts
# the product and, besides running whatever twins exist, asks the feature's own
# entry point two plain questions and writes down the answers. It COMPARES
# NOTHING and SCORES NOTHING: the words go on the card so a person can read
# what the finished feature actually does before saying merge.
#
# Where the entry point comes from: the per-feature live-check file this branch
# added under qa/gates/ already carries the method and path, filled in at
# planning time. Nothing is guessed — with no such file, or more than one, this
# says so and observes nothing.
#
# UNRESOLVED, and said plainly wherever this is described: choosing useful
# questions for an arbitrary feature. This asks the entry point in its two
# plainest states (nothing stored, then a few records made through the
# product's own interface). That will not always expose a fault, which is why
# the card carries what was ASKED as well as what came back.
# ---------------------------------------------------------------------------

_GATE_FILES_NOT_A_FEATURES_OWN = {
    "feature_behaviour_gate.py",   # the unfilled template
    "local_live_gate.py",
    "hurl_twin_gate.py",
    "dcl_gate.py",
    "health_gate.py",
}


def _git(root: Path, *args: str) -> Optional[str]:
    import subprocess

    try:
        done = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception:  # noqa: BLE001 — no git, or it would not run
        return None
    if done.returncode != 0:
        return None
    return done.stdout


def _base_ref(root: Path) -> Optional[str]:
    import os

    named = os.environ.get("GUARDKIT_BASE_BRANCH", "").strip()
    candidates = [named] if named else []
    candidates += ["main", "master", "origin/main", "origin/master"]
    for ref in candidates:
        if not ref:
            continue
        if _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"):
            return ref
    return None


def _gate_candidates_from_branch(root: Path) -> Tuple[List[str], Optional[str]]:
    """Live-check files this branch added or changed, against its base."""
    base = _base_ref(root)
    if base is None:
        return [], "this working copy has no base branch to compare against"
    out = _git(root, "diff", "--name-only", f"{base}...HEAD", "--", "qa/gates/")
    if out is None:
        out = _git(root, "diff", "--name-only", base, "HEAD", "--", "qa/gates/")
    if out is None:
        return [], f"the branch could not be compared with {base}"
    names = []
    for rel in out.splitlines():
        rel = rel.strip()
        if not rel.endswith("_gate.py"):
            continue
        leaf = Path(rel).name
        if leaf.startswith("_") or leaf in _GATE_FILES_NOT_A_FEATURES_OWN:
            continue
        if (root / rel).is_file() and rel not in names:
            names.append(rel)
    return names, None


def _gate_candidates_from_registry(root: Path) -> List[str]:
    """Live-check files registered on this branch and not on its base."""
    try:
        import yaml
    except Exception:  # noqa: BLE001
        return []

    def ids_and_paths(text: Optional[str]) -> Dict[str, str]:
        if not text:
            return {}
        try:
            data = yaml.safe_load(text)
        except Exception:  # noqa: BLE001
            return {}
        rows = (data or {}).get("gates") if isinstance(data, dict) else None
        found: Dict[str, str] = {}
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and row.get("id") and row.get("path"):
                    found[str(row["id"])] = str(row["path"])
        return found

    registry = root / "qa" / "gates" / "registry.yaml"
    if not registry.is_file():
        return []
    head = ids_and_paths(registry.read_text(encoding="utf-8"))
    base = _base_ref(root)
    before = ids_and_paths(
        _git(root, "show", f"{base}:qa/gates/registry.yaml") if base else None
    )
    added = []
    for gate_id, rel in head.items():
        if gate_id in before:
            continue
        leaf = Path(rel).name
        if leaf.startswith("_") or leaf in _GATE_FILES_NOT_A_FEATURES_OWN:
            continue
        if (root / rel).is_file() and rel not in added:
            added.append(rel)
    return added


def _spec_of(path: Path) -> Optional[Dict[str, Any]]:
    """The SPEC block of a live-check file, READ and never executed."""
    import ast

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "SPEC":
                try:
                    value = ast.literal_eval(node.value)
                except Exception:  # noqa: BLE001
                    return None
                return value if isinstance(value, dict) else None
    return None


def cmd_entry_point(root_path: str) -> int:
    root = Path(root_path).resolve()
    names, why = _gate_candidates_from_branch(root)
    source = "what this branch changed under qa/gates/"
    if not names:
        names = _gate_candidates_from_registry(root)
        source = "qa/gates/registry.yaml"
    if not names:
        print(json.dumps({
            "found": False,
            "reason": (
                "this branch added no live-check file of its own under "
                "qa/gates/, so this check does not know which entry point the "
                "feature delivered" + (f" ({why})" if why else "")
            ),
        }))
        return 0
    if len(names) > 1:
        print(json.dumps({
            "found": False,
            "reason": (
                f"this branch added {len(names)} live-check files under "
                f"qa/gates/ ({', '.join(sorted(names))}), so which one is the "
                "feature's own entry point is ambiguous and nothing was asked"
            ),
        }))
        return 0
    rel = names[0]
    spec = _spec_of(root / rel)
    request = (spec or {}).get("request") if isinstance(spec, dict) else None
    path_value = request.get("path") if isinstance(request, dict) else None
    if not isinstance(path_value, str) or not path_value.strip():
        print(json.dumps({
            "found": False,
            "reason": f"{rel} names no request path, so nothing was asked",
        }))
        return 0
    if path_value.strip() == "/REPLACE_ME":
        print(json.dumps({
            "found": False,
            "reason": f"{rel} was never filled in, so nothing was asked",
        }))
        return 0
    method = request.get("method") if isinstance(request, dict) else None
    print(json.dumps({
        "found": True,
        "method": (method if isinstance(method, str) and method.strip() else "GET").upper(),
        "path": path_value.strip(),
        "source": rel,
        "found_from": source,
    }))
    return 0


# ----------------------------------------------------------- the observations

_ANSWER_LIMIT = 300


def _shorten(text: str, limit: int = _ANSWER_LIMIT) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _request(
    url: str,
    method: str = "GET",
    body: Optional[bytes] = None,
    timeout: float = 30.0,
    limit: int = 8192,
) -> Tuple[Optional[int], str]:
    """One request, its status and a reading of what came back.

    ``limit`` bounds how much is read. It is small for an observation, whose
    answer is shortened anyway, and large for the product's own published
    description, which must be read WHOLE or it cannot be parsed at all — an
    8 KB cut of it was why the first Stage B run could create no records.
    """
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = response.read(limit).decode("utf-8", errors="replace")
            return response.status, payload
    except urllib.error.HTTPError as exc:
        try:
            payload = exc.read(4096).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            payload = ""
        return exc.code, payload
    except Exception as exc:  # noqa: BLE001 — a product that will not answer
        return None, f"no answer ({exc})"


def _answered(status: Optional[int], payload: str) -> str:
    if status is None:
        return _shorten(payload)
    return _shorten(f"HTTP {status}: {payload}" if payload else f"HTTP {status}")


def _published_description(base_url: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """The product's own description of its interface, or why there is none."""
    status, payload = _request(
        base_url.rstrip("/") + "/openapi.json", limit=4 * 1024 * 1024
    )
    if status != 200:
        return None, (
            "the product answered "
            + ("nothing" if status is None else f"HTTP {status}")
            + " at /openapi.json"
        )
    try:
        data = json.loads(payload)
    except Exception as exc:  # noqa: BLE001
        return None, f"the product's description at /openapi.json could not be read ({exc})"
    if not isinstance(data, dict):
        return None, "the product's description at /openapi.json is not a mapping"
    return data, ""


def _resolve(schema: Any, doc: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
    if not isinstance(schema, dict) or depth > 4:
        return {}
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        node: Any = doc
        for part in ref[2:].split("/"):
            if not isinstance(node, dict):
                return {}
            node = node.get(part)
        return _resolve(node, doc, depth + 1)
    return schema


def _create_call(doc: Dict[str, Any], entry_path: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """The product's own call for making a record of the kind this feature counts.

    Only a call whose path is a STRICT parent of the feature's entry point is
    used ("/users" for "/users/created-per-day"). Anything else would be this
    check guessing at the product, and a guess is what it is here to stop.
    """
    paths = doc.get("paths")
    if not isinstance(paths, dict):
        return None
    entry = entry_path.rstrip("/")
    best: Optional[Tuple[str, Dict[str, Any]]] = None
    for path_name, operations in paths.items():
        if not isinstance(path_name, str) or not isinstance(operations, dict):
            continue
        post = operations.get("post")
        if not isinstance(post, dict):
            continue
        parent = path_name.rstrip("/")
        if "{" in parent or not parent:
            continue
        if parent == entry or not entry.startswith(parent + "/"):
            continue
        if best is None or len(parent) > len(best[0]):
            best = (path_name, post)
    return best


def _create_body(post: Dict[str, Any], doc: Dict[str, Any], marker: str, index: int) -> Optional[bytes]:
    body = post.get("requestBody")
    if not isinstance(body, dict):
        return None
    content = body.get("content")
    if not isinstance(content, dict):
        return None
    json_body = content.get("application/json")
    if not isinstance(json_body, dict):
        return None
    schema = _resolve(json_body.get("schema"), doc)
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None
    required = schema.get("required")
    wanted = [n for n in required if isinstance(n, str)] if isinstance(required, list) else list(properties)
    fields: Dict[str, Any] = {}
    for name in wanted[:8]:
        definition = _resolve(properties.get(name), doc)
        kind = definition.get("type")
        if isinstance(kind, list):
            kind = next((k for k in kind if k != "null"), "string")
        if kind in ("integer", "number"):
            fields[name] = index
        elif kind == "boolean":
            fields[name] = True
        elif kind in (None, "string"):
            if definition.get("format") == "email" or "email" in name.lower():
                fields[name] = f"observation-{marker}-{index}@example.com"
            else:
                fields[name] = f"observation {marker} {index}"
        else:
            return None
    if not fields:
        return None
    return json.dumps(fields).encode("utf-8")


def cmd_observe(base_url: str, entry_file: str) -> int:
    import os

    out: Dict[str, Any] = {"observations": [], "not_checked": []}

    def say(asked: str, answered: str) -> None:
        out["observations"].append({"asked": asked, "answered": answered})

    def cannot(reason: str) -> None:
        out["not_checked"].append({
            "name": "what the finished feature answers",
            "reason": reason,
        })

    try:
        entry = json.loads(Path(entry_file).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        entry = {"found": False, "reason": f"the entry point could not be read ({exc})"}
    if not isinstance(entry, dict) or not entry.get("found"):
        cannot(str((entry or {}).get("reason") or "the feature's entry point was not found"))
        print(json.dumps(out))
        return 0

    base = base_url.rstrip("/")
    method = str(entry.get("method") or "GET").upper()
    path = str(entry.get("path") or "")
    url = base + path
    marker = f"fc{os.getpid()}"

    status, payload = _request(url, method=method)
    say(f"{method} {path}, with nothing stored", _answered(status, payload))

    doc, why = _published_description(base)
    if doc is None:
        cannot(
            "no records could be created and the entry point was asked only on "
            f"an empty database: {why}"
        )
        print(json.dumps(out))
        return 0
    call = _create_call(doc, path)
    if call is None:
        cannot(
            "the product's published interface offers no create call under "
            f"{path or 'the entry point'}, so no records could be created and "
            "the entry point was asked only on an empty database"
        )
        print(json.dumps(out))
        return 0

    create_path, post = call
    made = 0
    statuses: List[str] = []
    for index in (1, 2, 3):
        body = _create_body(post, doc, marker, index)
        if body is None:
            break
        code, _ = _request(base + create_path, method="POST", body=body)
        statuses.append("no answer" if code is None else str(code))
        if code is not None and 200 <= code < 300:
            made += 1
    if not statuses:
        cannot(
            f"the product's own create call at {create_path} asks for something "
            "this check could not fill in, so no records were created"
        )
        print(json.dumps(out))
        return 0

    say(
        f"POST {create_path} x{len(statuses)} (the product's own create call)",
        "answered " + ", ".join(statuses),
    )
    status, payload = _request(url, method=method)
    say(
        f"{method} {path}, after {made} record(s) were created",
        _answered(status, payload),
    )
    print(json.dumps(out))
    return 0


def cmd_table(tsv_path: str) -> int:
    """Print a TAB-separated file as aligned columns, cutting nothing.

    Not `column -t`: outside a UTF-8 locale that tool rewrites every accented
    character as a \\xNN escape, so a French scenario title came out as
    mojibake. Padding is counted in CHARACTERS here, and no column has a fixed
    width, so a long or accented title is printed whole.
    """
    path = Path(tsv_path)
    try:
        rows = [
            line.split("\t")
            for line in path.read_text(encoding="utf-8").splitlines()
        ]
    except OSError as exc:
        print(f"feature-check: could not read the results table ({exc})", file=sys.stderr)
        return 1
    if not rows:
        return 0
    width = max(len(row) for row in rows)
    widths = [0] * width
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    for row in rows:
        parts = []
        for index, cell in enumerate(row):
            parts.append(cell if index == len(row) - 1 else cell.ljust(widths[index]))
        print("  ".join(parts).rstrip())
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
    if mode == "json-line" and 3 <= len(argv) <= 5:
        return cmd_json_line(*argv[2:5])
    if mode == "could-not-run" and len(argv) == 3:
        return cmd_could_not_run(argv[2])
    if mode == "entry-point" and len(argv) == 3:
        return cmd_entry_point(argv[2])
    if mode == "observe" and len(argv) == 4:
        return cmd_observe(argv[2], argv[3])
    if mode == "report-requests" and len(argv) == 3:
        return cmd_report_requests(argv[2])
    if mode == "table" and len(argv) == 3:
        return cmd_table(argv[2])
    _fail(f"feature-check: feature_check_twins.py does not understand {' '.join(argv[1:])!r}")
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
