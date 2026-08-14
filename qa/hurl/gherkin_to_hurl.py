#!/usr/bin/env python3
"""Gherkin worked-examples -> Hurl compiler (HTTP interface-kind executor).

Reads the accepted .feature (human-curated via propose-review) AND the DEPLOYED
app's OpenAPI contract, and asks a local model to emit a Hurl scenario that
exercises the behaviour over the wire against the REAL contract. The pilot's
lesson is baked in: guessing the response envelope/domain fails, so the compiler
is grounded on the live /openapi.json, and its output is gated twice — hurlfmt
--check (syntax) and running it over the wire (semantics).

Not a replacement for the human control point: propose-review still authors the
scenarios. This mechanises only the scenario -> over-the-wire translation that
pytest-bdd step definitions do by hand, with no per-language glue.

Usage:
  gherkin_to_hurl.py --feature F.feature --openapi-url http://host/openapi.json \
      --marker-var marker --out out.hurl [--model qwen36-workhorse]
"""
from __future__ import annotations
import argparse, json, os, re, sys, urllib.request

LLM_ENDPOINT = os.environ.get("COMPILER_LLM_ENDPOINT", "http://localhost:9000/v1/chat/completions")
LLM_MODEL = os.environ.get("COMPILER_LLM_MODEL", "qwen36-workhorse")

SYSTEM = """You compile a domain-language acceptance scenario into a Hurl file that verifies it OVER HTTP against a real deployed API. You are given the app's OpenAPI spec as ground truth — use its exact paths, request schemas, status codes, and response field names. Never guess field names or envelopes; read them from the spec.

Rules:
- Emit ONLY valid Hurl 8.x syntax. No prose, no markdown fences.
- Use {{host}} for the base URL and {{MARKER}} for the per-run unique marker where the scenario needs a unique value.
- One request block per HTTP interaction: METHOD {{host}}/path, optional headers, optional JSON body, then the expected `HTTP <status>` line, then optional [Captures] and [Asserts].
- Capture ids you need later: [Captures]\\n  name: jsonpath "$.id"
- Assert with jsonpath against the REAL response field names from the spec.
- CRITICAL: inside [Asserts], NEVER prefix a query with a name — write `jsonpath "$.x" == "y"`, never `name: jsonpath ...`. Named queries appear ONLY in [Captures].
- If a Given is NOT an HTTP step (e.g. "seeded directly into the database"), emit a Hurl COMMENT line `# delegated-to-wrapper: <text>` instead of faking an HTTP call — do not invent an endpoint.
- Keep the whole scenario self-contained (Hurl has no includes/cross-file state)."""

def fetch_openapi(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read().decode())

def parse_scenarios(feature_text: str) -> list[tuple[str, list[str]]]:
    scenarios, cur, steps = [], None, []
    for line in feature_text.splitlines():
        s = line.strip()
        if s.startswith("Scenario:"):
            if cur: scenarios.append((cur, steps))
            cur, steps = s[len("Scenario:"):].strip(), []
        elif re.match(r"^(Given|When|Then|And|But) ", s):
            steps.append(s)
    if cur: scenarios.append((cur, steps))
    return scenarios

def call_llm(system: str, user: str, retries: int = 3) -> str:
    body = json.dumps({"model": LLM_MODEL, "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(LLM_ENDPOINT, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                out = json.loads(r.read().decode())
            break
        except (urllib.error.URLError, TimeoutError, OSError) as e:  # slow/contended local seat
            last = e
            print(f"  llm call timed out (attempt {attempt+1}/{retries}), retrying...", file=sys.stderr)
    else:
        raise RuntimeError(f"llm call failed after {retries} retries: {last}")
    txt = out["choices"][0]["message"]["content"]
    # strip any accidental fences (defensive — same class as the coach fence bug)
    txt = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", txt.strip())
    return txt

def hurlfmt_ok(hurl_text: str) -> tuple[bool, str]:
    """Syntax-gate a Hurl block with hurlfmt --check. Returns (ok, error_text)."""
    import subprocess, tempfile
    hb = os.environ.get("HURLFMT_BIN", os.path.expanduser("~/.local/bin/hurlfmt"))
    with tempfile.NamedTemporaryFile("w", suffix=".hurl", delete=False) as f:
        f.write(hurl_text); path = f.name
    try:
        p = subprocess.run([hb, "--check", path], capture_output=True, text=True, timeout=30)
        return p.returncode == 0, (p.stderr or p.stdout)
    finally:
        os.unlink(path)


def compile_scenario(name: str, steps: list[str], spec_json: str, marker_var: str,
                     max_repairs: int = 2) -> str:
    """Generate one scenario's Hurl block, then fix-and-re-verify against hurlfmt
    up to max_repairs times — the fix-and-re-verify law applied to the compiler."""
    user = (f"OpenAPI spec (ground truth):\n{spec_json}\n\n"
            f"Scenario: {name}\n" + "\n".join(steps) +
            f"\n\nMarker variable name: {marker_var}. Emit the Hurl block for THIS scenario only.")
    hurl = call_llm(SYSTEM, user).strip()
    for attempt in range(max_repairs):
        ok, err = hurlfmt_ok(hurl)
        if ok:
            return hurl
        # feed the syntax error back — repair, don't discard
        repair = (f"The Hurl you produced fails hurlfmt with this error:\n{err.strip()[:600]}\n\n"
                  f"Here is the Hurl:\n{hurl}\n\nReturn ONLY the corrected Hurl block, valid Hurl 8.x syntax.")
        hurl = call_llm(SYSTEM, repair).strip()
    ok, err = hurlfmt_ok(hurl)
    if not ok:
        hurl = f"# COMPILE-FAIL after {max_repairs} repairs (hurlfmt): {err.strip()[:150]}\n" + hurl
    return hurl


def compile_feature(feature_path: str, openapi: dict, marker_var: str) -> str:
    scenarios = parse_scenarios(open(feature_path).read())
    slim = {"paths": openapi.get("paths", {}), "components": openapi.get("components", {})}
    spec_json = json.dumps(slim, separators=(",", ":"))[:24000]
    blocks = [f"# Compiled from {os.path.basename(feature_path)} against the deployed OpenAPI contract.",
              f"# Human-curated scenarios (propose-review); HTTP translation is machine-generated, hurlfmt-repaired, then run-verified."]
    for name, steps in scenarios:
        hurl = compile_scenario(name, steps, spec_json, marker_var)
        blocks.append(f"\n# --- Scenario: {name} ---\n{hurl.strip()}")
    return "\n".join(blocks) + "\n"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature", required=True)
    ap.add_argument("--openapi-url", required=True)
    ap.add_argument("--marker-var", default="MARKER")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    openapi = fetch_openapi(a.openapi_url)
    hurl = compile_feature(a.feature, openapi, a.marker_var)
    open(a.out, "w").write(hurl)
    print(f"wrote {a.out} ({len(hurl.splitlines())} lines) from {a.openapi_url}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
