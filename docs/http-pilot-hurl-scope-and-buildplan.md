# HTTP verification pilot — Gherkin worked-examples → Hurl, over the wire · Scope + Build Plan
## For: coordinator design-build + honest A/B (NOT full factory orchestration — this is a mechanism experiment)
## Status: DESIGN-READY 2026-07-25 · Rich's go: "go with the HTTP pilot" · GATED on the command socket (FEAT-8AD1 fix B) merging into guardkit main
## Ruling embodied: docs/verification-prior-art-evidence-2026-07-25.md §6 (HTTP executor = Hurl) + the deep-dive dossier's mapping recipe + cannot-map fences

## 1. What and why (one minute)

The verification research ruled the HTTP interface-kind's executor is Hurl: accepted worked
examples (from Rich's Gherkin propose–review) compile to plain-text over-the-wire scenarios
instead of pytest-bdd step-definition glue. This pilot proves that on ONE real feature, A/B,
with receipts — and doubles as the **first real user of the command socket**
(`behavioural_oracle.command`, built in FEAT-8AD1): the `.hurl` runs via a declared shell
command, not a Python file, so a green pilot also proves the non-Python cure on a live oracle.

Target: api_test's `/users` round-trip (the same behaviour the runtime-smoke oracle already
verifies in Python). We express those probes as Hurl and compare — same deployed sandbox, same
seeded data, over the wire either way.

## 2. Deliverables (all in api_test)

1. **`qa/hurl/users_roundtrip.hurl`** — the accepted worked examples compiled to Hurl against
   the real `/users` contract (email + full_name; 201/200/404/409/422): create-with-marker →
   capture id → GET listing contains the marker → GET /users/{id} reads back identical →
   GET /users/{random-uuid} is 404 → duplicate-email POST is 409 → malformed POST is 422.
   Uses `{{host}}` + `{{run_id}}` variables; `--report-json` for the receipt.
2. **`qa/hurl/run_hurl_oracle.sh`** — the socket wrapper (the command behind
   `behavioural_oracle.command`): (a) the non-HTTP Given — nothing to seed here since the
   marker is created *through* the product API, but the wrapper is where a psql seed WOULD live
   per the dossier; (b) mint a fresh receipts dir (Hurl reports APPEND — cannot-map fence);
   (c) `hurl --variable host=… --variable run_id=<fresh> --report-json <dir> users_roundtrip.hurl`;
   (d) map Hurl's exit tri-state to the oracle: 0 pass · 4 app-failed-spec · 3 app-down ·
   2 malformed-oracle-file (generator bug, not app bug — surfaced distinctly). Exit 0/1 to the
   socket; the JSON report is the evidence.
3. **The A/B record** — `docs/http-pilot-hurl-results-2026-07-25.md`: for each probe, does Hurl
   catch what `users_roundtrip.py` catches? Lines of plumbing each side. Does Hurl survive the
   mocked-green problem (yes by construction — over the wire). The honest cannot-map list
   observed in practice.

## 3. Binding constraints (the fences from the dossier, verbatim)

- Scenario self-containment: no cross-file/cross-scenario Hurl state (Hurl has no includes) —
  the whole round-trip is ONE self-contained `.hurl`.
- Fresh receipts dir per run (Hurl reports append).
- `hurlfmt --check` gates the `.hurl` before any sandbox spins (zero-network transcription gate).
- The seed/Given that is NOT an HTTP step lives in the wrapper, never faked as an HTTP call.
- Streaming (SSE/WebSocket) is out of scope — this contract has none; noted as a kind-limit.
- The Python oracle stays in place unchanged — this is an A/B beside it, not a replacement.
  Nothing retires until the A/B earns it (repo-by-repo retirement law).

## 4. Sequence (the one real dependency)

1. **FEAT-8AD1 merges** (fix B = `behavioural_oracle.command` lands in guardkit main). Until
   then the wrapper can be exercised by hand but not discovered by the factory as an oracle.
2. Coordinator writes deliverables 1–2, drives them by hand against the running sandbox
   (`hurl` is installed at `~/.local/bin/hurl`, 8.0.1 aarch64), captures the A/B record.
3. If green: propose the Gherkin→Hurl compiler as the next mechanism lane (this pilot is the
   hand-built proof; the compiler is the generalization).

## 5. Done means

The Hurl oracle runs green over the wire against the deployed api_test sandbox by the
coordinator's own hand; the A/B record honestly compares catch-parity and plumbing-cost vs the
Python probe; and — once FEAT-8AD1 is merged — the same `.hurl` runs as a discovered oracle via
`behavioural_oracle.command`, proving the socket carries a non-Python runtime check end to end.

## Status Log
| step | status | date | commit |
|---|---|---|---|
| scope+design | DESIGN-READY (gated on FEAT-8AD1) | 2026-07-25 | — |
| hurl 8.0.1 installed ~/.local/bin | done | 2026-07-25 | — |
