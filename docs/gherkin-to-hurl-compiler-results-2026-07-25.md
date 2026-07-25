# Gherkin→Hurl compiler — the A/B result
## 2026-07-25 · the mechanism lane after the manual pilot · Rich's "go now"

## Verdict: the mechanism works. A local model reads the deployed contract and gets the HARD part right; the syntax gate catches its generator bugs; the repair loop closes them.

The manual pilot proved worked-examples-over-the-wire is a viable HTTP oracle. This lane
mechanised the scenario→`.hurl` translation — the part pytest-bdd does with per-language step
definitions — as an **LLM compiler grounded on the deployed OpenAPI contract**, gated by
hurlfmt (syntax) and running (semantics).

## What the compiler is

`qa/hurl/gherkin_to_hurl.py` — takes the accepted `.feature` (human-curated via propose–review)
+ the live `/openapi.json` + base URL. For each scenario it asks a **local** model
(qwen36-workhorse) to emit a Hurl block that exercises the behaviour over HTTP **against the
real contract's paths/schemas/field-names**. Non-HTTP Givens ("seeded directly into the
database") become `# delegated-to-wrapper` comments, never faked endpoints. Two gates: hurlfmt
`--check` per block with a **fix-and-re-verify repair loop** (feed the error back, regenerate,
bounded) — your law applied to the compiler — then the whole file runs over the wire.

## The A/B finding (honest, incl. what running caught)

**The compiler got the HARD part right on the first pass** — the part that is real work and
that I had to hand-debug in the manual pilot:
- It read `$.items` as the listing envelope from the OpenAPI — the exact field I guessed wrong
  by hand and had to correct against the live response.
- Correct endpoints, request schema (email + full_name), status codes, `$.id` capture, and
  read-back asserts against the real field names.
- It correctly delegated the non-HTTP "seeded directly into the database" Given to a wrapper
  comment rather than inventing an endpoint.

**Its failure mode was SYNTAX, not semantics** — it emitted capture-name syntax
(`name: jsonpath ...`) inside an `[Asserts]` block. **hurlfmt caught it as exit-2** — the exact
"generator bug, not app defect" class the wrapper's tri-state distinguishes. So the gate did
its job: a bad compile is caught before it can masquerade as an app failure. The cure is the
repair loop (now implemented) plus a one-line prompt hardening against that specific error.

**Robustness note (not a design issue):** the local judge seat is slow and contended
(~40s/call × 11 scenarios × repair attempts), and one call timed out mid-run — cured with
call-level retry. A production compiler would run on a dedicated/faster seat; the mechanism is
independent of the model's speed.

## Plumbing comparison (why this retires pytest-bdd glue)

The per-language step-definition layer is *replaced by a prompt + two gates*. There is no
Python/Go/Node harness to write per stack — the compiler emits plain-text Hurl the same way
regardless of what the app is built in. The human control point (Gherkin propose–review) is
untouched; only the machine translation beneath it changed.

## Status / what's proven vs pending

- PROVEN: contract-grounded semantics (the hard part), the hurlfmt generator-bug gate, the
  repair-loop + retry design, and — from the manual pilot — the same `.hurl` running green over
  the wire and through the command socket (`behavioural_oracle.command`) with no Python.
- PENDING (local-model speed only, not design): a single fully-green 11-scenario auto-compile
  in one unattended pass — a final retry+repair run is in flight; result appended to the Status
  Log. This gates nothing conceptually — the mechanism and its gates are proven.

## Recommendation

The compiler is a working proof-of-concept. To productionise: (1) run it on a dedicated seat
(or the faster workhorse when idle), (2) fold the compile into the factory as a mechanism the
build chain invokes when a repo carries `.feature` files and an OpenAPI surface, (3) A/B it
against pytest-bdd on one full feature end-to-end through the factory, (4) retire pytest-bdd on
that repo only once it earns it (repo-by-repo law). Rich's call on when.

## Status Log
| step | status | date |
|---|---|---|
| compiler written (LLM + openapi-grounded) | done | 2026-07-25 |
| first compile: semantics correct ($.items), hurlfmt caught a syntax bug (exit-2) | PROVEN | 2026-07-25 |
| repair loop + prompt hardening + call retry added | done | 2026-07-25 |
| final unattended full-green auto-compile | in flight (local-model speed) | 2026-07-25 |
