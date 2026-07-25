# HTTP pilot — Gherkin worked-examples → Hurl: the A/B result
## 2026-07-25 · driven by the coordinator's own hand against a live api_test deployment

## Verdict: the HTTP executor works, and it rode the command socket end to end.

The `/users` round-trip — the same behaviour `tests/acceptance/users_roundtrip.py` verifies in
Python — was re-expressed as a single self-contained `.hurl` file, run over the wire against a
live api_test deployment, and produced a passing behavioural-oracle result **through
`behavioural_oracle.command`** (fix B, merged `58bc42b6` an hour earlier) with **no Python
oracle file present**. So this pilot is two proofs in one: Hurl is a viable HTTP-kind executor,
and the command socket carries a real non-Python runtime check in production.

## Catch-parity (does Hurl catch what the Python probe catches?)

Yes — same seven behaviours: create-with-marker (201), listing contains the marker (200),
POST→GET read-back identical, unknown-id 404, duplicate-email 409, malformed 422. And a live
demonstration of parity: **Hurl independently surfaced the exact `.local`-TLD email-validation
rejection the Python oracle had already had to debug** (it is in the runtime-smoke Status Log
as ".local → .internal"). Both executors see the same real app behaviour because both go over
the wire.

## Plumbing cost (the point of retiring pytest-bdd glue)

| side | files | lines |
|---|---|---|
| **Hurl** | `users_roundtrip.hurl` + `run_hurl_oracle.sh` | **64 + 33 = 97** |
| Python probe | `qa/smoke/probe.py` + `tests/acceptance/users_roundtrip.py` | 271 + 331 = 602 |

The Hurl scenario is ~6× less code, and the 64-line `.hurl` is **declarative and diffable** —
it reads as the worked examples, not as a program. No step-definition glue, no per-language
harness. `hurlfmt --check` gated the transcription before any deploy (a zero-network catch).

## Mocked-green resistance

By construction: the `.hurl` speaks only HTTP to the deployed app. There is no in-process seam
to mock — a stubbed implementation cannot make the seeded marker appear in the listing over the
wire. This is the property the whole runtime layer exists for.

## What the pilot surfaced honestly (the transcription-accuracy lesson)

Two authoring errors, both caught within seconds of the first real run (not by review, by
running): the listing envelope is `items` not `users`, and the `.local` domain is rejected.
These are exactly the mapping details a Gherkin→Hurl **compiler** would need to get from the
real response shape — the argument for the compiler reading the deployed contract, not guessing.
No cannot-map fence was hit on this contract (no streaming; the seed is created through the
product API, so nothing needed the wrapper's pre-seed slot).

## Recommendation

The HTTP-kind executor is proven. Next step (Rich's call): build the **Gherkin→Hurl compiler**
as a small mechanism lane — accepted worked examples → `.hurl`, reading the deployed response
shape for accuracy — and run it A/B against pytest-bdd on one real feature end to end through
the factory. pytest-bdd retires on that repo only once the compiler earns it (repo-by-repo law).
Nothing here removes the Python oracle; it ran beside it.

## Receipts
- `qa/hurl/users_roundtrip.hurl` (the worked examples over the wire), `qa/hurl/run_hurl_oracle.sh`
  (the socket wrapper, exit tri-state).
- Discovered-oracle proof: `_produce_behavioural_oracle` with the wrapper as
  `behavioural_oracle.command`, no `*_roundtrip.py` → `status=ran passed=True`.
- Ephemeral pilot stack `apitest-hurl-pilot` deployed + torn down clean; live `apitest-f2`
  untouched throughout.
