#!/usr/bin/env python3
"""Local live-gate driver — supplies the F16 seam that `guardkit qa live-gate`
leaves unwired in v1.

WHY THIS EXISTS: guardkit's pre-flight (guardkit/orchestrator/live_gate/
preflight.py) ALWAYS consults an F16 perishable-prereq checklist provider, but
the `guardkit qa live-gate` CLI injects none — so the plain CLI short-circuits
to verdict `environment_fail` (exit 4) BEFORE any gate script runs, on every
repo, regardless of how healthy the deployment is. (The F16 schema is WS5-owned;
only guardkit's own tests inject a provider.) That is a guardkit-side v1 gap,
not an api_test authoring gap — the registered gate scripts themselves pass.

WHAT THIS DOES: constructs the SAME, UNMODIFIED guardkit LiveGateRunner but wires
a minimal HONEST F16 provider for this API-only app — it probes GET
{API_TEST_BASE_URL}/health once (the only perishable prereq here; there is no
broker/token/model to warm) and, when the app answers 200, lets the real runner
execute the registered F4 gates against the live compose deployment and emit the
genuine results envelope (+ qa/gates/history/<run_id>.json and the evidence dir).
Identical envelope shape, verdict, and exit-code semantics as the CLI.

    python3 qa/gates/local_live_gate.py --feature <id> --target local [--gates health]

If/when guardkit gains a CLI hook for the F16 provider (or a real WS5 F16
source), this driver retires in favour of `guardkit qa live-gate`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from guardkit.orchestrator.live_gate.preflight import F16ChecklistProvider, SeamResult
from guardkit.orchestrator.live_gate.runner import LiveGateRunner

_VERDICT_EXIT = {"pass": 0, "fail": 1, "instrument_fail": 3, "environment_fail": 4}


class HealthProbeF16(F16ChecklistProvider):
    """Honest F16 for an API-only app: the sole perishable prereq is 'the app is
    up', proven by a real GET /health probe. No broker/tokens/models to check."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def checklist(self):
        url = self.base_url + "/health"
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                ok = resp.status == 200
                return [SeamResult(
                    ok=ok,
                    detail=(f"F16 perishable readiness: GET {url} -> {resp.status} "
                            f"(API-only app: no broker/tokens/models to warm)"),
                )]
        except Exception as exc:
            return [SeamResult(ok=False, detail=f"F16 perishable readiness: GET {url} failed: {exc}")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--feature", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--gates", default=None, help="comma-separated gate id subset")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()

    base_url = os.environ.get("API_TEST_BASE_URL", "http://localhost:8901")
    runner = LiveGateRunner(Path(args.repo), f16_provider=HealthProbeF16(base_url))
    requested = [g.strip() for g in args.gates.split(",") if g.strip()] if args.gates else None

    envelope = runner.run(args.feature, args.target, requested_gate_ids=requested)
    print(json.dumps(envelope.model_dump(mode="json"), indent=2))
    sys.exit(_VERDICT_EXIT.get(envelope.verdict, 1))


if __name__ == "__main__":
    main()
