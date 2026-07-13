# Coverage cross-check — DCL-derived assertions vs Gherkin vs pass-bar (DCL SPIKE, S3)

Three-way cross-check: what each source **demands**, what the DCL-derived set **covers**, what it
**misses**, and what it covers that the others do not. This is the coverage evidence for the
re-aimed pass/kill (`dcl-factory-evaluation-2026-07.md` §7): *do the derived outside-in assertions
cover at least the scenarios' real verification power, with zero per-stack glue?* **This file records
coverage facts; it does not pronounce pass/kill — that is S5 + Rich's attended call.**

## Note on the three sources

- **Derived set:** the 11 assertion concepts in `derivation-rules.md` (9 RUN + 1 SKIP + 1 MISS),
  each traced to a DCL block. Run receipt: `RUN-RECEIPT.md` (9/9 RUN PASS).
- **Gherkin:** `features/stats-endpoint/stats-endpoint.feature` — **8** scenarios tagged
  `@task:TASK-STAT-001` (of which **3** are `@key-example`). *Discrepancy flagged honestly:* the
  handoff §0 twice says "the 3 `@task:TASK-STAT-001` scenarios"; the file on disk has **8** (3
  key-examples + 2 boundary + 1 negative + 2 edge-case). The cross-check is done against the **8 on
  disk** (ground truth), with the 3 key-examples marked. The Gherkin is **never wired to execute**
  (gap H-08) — so its "verification power" is the *intended* checks, not a passing run.
- **Pass-bar:** `qa/pass-bar-TASK-STAT-001.yaml` — 5 machine criteria + 2 negative paths. This one
  **is** live (the Factory-2 live-gate, 14/14 on `a58bf31`).

---

## A · Derived set vs the pass-bar (the live gate)

| Pass-bar demand | Derived coverage | Verdict |
|---|---|---|
| **C-STATS-200** — 200 + standard response headers | A-OUTCOME asserts 200. **Headers not covered** (DCL has no header concept). | **PARTIAL** |
| **C-STATS-FIELDS** — exactly `service` (non-empty str), `requests_served` (integer), `first_request_at` | A-FIELD-SVC + A-FIELD-REQ + A-FIELD-FRA cover presence+type. **"exactly" (no extra fields) not enforced**; **integer-ness is `[J4]`**, checked opportunistically but not DCL-derivable. | **MOSTLY** |
| **C-STATS-COUNTS** — `requests_served` **strictly** increases across two calls | A-COUNT-MONO asserts **non-decreasing** only; strict-increase is `[J7]` (DCL `count` ⊉ strict-monotone). | **PARTIAL (weaker)** |
| **C-STATS-FIRST-AT** — non-null once handled, stable, UTC ISO-8601 | A-LIFE-SERVING (non-null) + A-LIFE-STABLE (stable) + A-FRA-FORMAT (ISO-8601, via `[J5]`). | **FULL** |
| **C-STATS-READONLY** — `POST /stats` → 405 | A-READONLY **MISS** — no `rule` block in the DCL to derive from. | **MISS** |
| neg: **dependency_down_degradation** — available when DB down | A-AVAIL **SKIP** — derivable from the `policy`, not runnable read-only (needs DB fault-injection `[J8]`). | **DERIVED, NOT RUN** |
| neg: **mutation_rejected_read_only** | = C-STATS-READONLY → **MISS**. | **MISS** |

## B · Derived set vs the 8 Gherkin scenarios

| # | Scenario (tag) | Derived coverage | Verdict |
|---|---|---|---|
| 1 | identity + activity returned (`@key-example @smoke`) | A-OUTCOME + A-FIELD-SVC + A-FIELD-REQ + A-FIELD-FRA | **FULL** |
| 2 | count increases as requests handled (`@key-example @smoke`) | A-COUNT-MONO (non-decrease; scenario wants "higher" = strict `[J7]`) | **PARTIAL (weaker)** |
| 3 | first-request time stable + UTC ISO-8601 (`@key-example`) | A-LIFE-STABLE + A-FRA-FORMAT | **FULL** |
| 4 | fresh service counts the stats request itself, ≥1 (`@boundary`) | not exercisable read-only (can't reach a fresh process); the DCL `Fresh` state has no runnable observable without a restart | **UNCOVERED** |
| 5 | count never decreases while running (`@boundary`) | A-COUNT-MONO — exact match | **FULL** |
| 6 | modifying not allowed / POST rejected (`@negative`) | A-READONLY **MISS** — no DCL `rule` | **MISS** |
| 7 | available when DB unavailable (`@edge-case`) | A-AVAIL **SKIP** — derivable from `policy`, not run | **DERIVED, NOT RUN** |
| 8 | restart begins a fresh count (`@edge-case`) | not exercisable read-only (can't restart the shared deploy); DCL lifecycle *comments* restart→Fresh but declares no construct that derives an assertion | **UNCOVERED** |

**Tally vs Gherkin (8):** FULL 3 · PARTIAL 1 · MISS 1 · DERIVED-NOT-RUN 1 · UNCOVERED 2.
Of the 3 `@key-example` scenarios (the load-bearing ones): 2 FULL, 1 PARTIAL — the derived set
covers the key-example core, weaker only on strict-vs-non-decreasing counting.

## C · What the derived set covers that the others do NOT

- **A-DURATION** (liveness/latency probe) — derived from the `observe capability duration` block;
  neither the Gherkin nor the pass-bar asserts any latency/liveness bound. *Honest caveat:* the
  bound (5 s) is `[J7]`-supplied, not from the DCL, so this is a weak extra — a probe the others
  lack, but not a threshold the DCL earned.
- **Machine-typed field schema** — the derived field checks trace to the DCL `event`'s *typed*
  fields (`service: Text`, `requestsServed: Number`), whereas the Gherkin expresses "a whole number"
  in prose. Marginal: the pass-bar already types the fields too, so this is only an edge over the
  Gherkin, not over the pass-bar.

---

## Coverage verdict (facts, not a pass/kill ruling)

1. **Zero per-stack glue — CLEAR.** The derived assertions run via stdlib `urllib`+`json`, no
   pytest / pytest-bdd / step-defs / conftest bridge / per-language plugin. Pass-condition (c) of
   §7 is met unambiguously (contrast `gherkin-glue-bill.md`, the unpaid glue the Gherkin side
   would need to execute at all).

2. **"Cover at least the scenarios' real verification power" — PARTIAL, with two named gaps.**
   The derived set **fully covers** the happy-path, per-field, stability, and format power (Gherkin
   1/3/5 FULL, 2 weaker; pass-bar C-STATS-FIRST-AT FULL, FIELDS mostly, 200 partial). It **fails to
   cover** two demands that *both* other sources make:
   - **The read-only / POST-405 negative (A-READONLY MISS)** — the decisive one. This is **not** a
     venue limit; it is a **DCL-expressiveness / authoring** limit: `capability.dcl` declares **no
     `rule` block**, so R9 (rule → negative-case) fired zero assertions. DCL's capability model
     centres on what the system *does* (outcomes, events, lifecycle), not on forbidding an HTTP verb
     — so "POST is rejected" has no natural first-class home, and deriving it would need hand-glue
     *outside* the DCL. This is squarely the §7 KILL-side signal ("the derivation needed
     step-definition-scale hand-glue, or the DCL added no checkable signal") **for this one
     criterion**, and it must be carried verbatim into the S5 head-to-head.
   - **The DB-down availability (A-AVAIL) and the two lifecycle-boundary scenarios (fresh-counts-itself,
     restart-resets)** — *derivable in shape* from the `policy`/`lifecycle` but **not runnable in
     the read-only HTTP venue** (they need fault-injection / a process restart). These are venue
     limits, not DCL limits — the pass-bar's own live-gate treats dependency-down as a "NO
     degradation" narrative rather than a fault-injected probe, so the gap is shared, not unique to
     DCL.

3. **The compiler caught a real (conformance) error** (S2 `compile-log.md`: the `optional` token,
   10-diagnostic cascade, precise line/column) — a check with **no Gherkin analogue**. But on a spec
   this simple it was a *syntax/conformance* catch, not a *requirement-coherence* catch; it did not
   surface a hidden `/stats` ambiguity. Recorded for the S5 "compiler catches" column.

**Net for S5/Rich:** on this feature the DCL-derived, zero-glue, outside-in path **reproduces the
core verification power** the Gherkin and pass-bar intend (fields, outcome, monotonicity, stability,
format) **but has one hard miss the others cover — the read-only negative — traceable to a DCL
authoring/expressiveness gap, plus venue-blocked availability/restart checks the pass-bar's own
live-gate also stops short of.** Whether that core-covered-with-one-hard-miss clears the §7 PASS bar
is the attended head-to-head call, not S3's to make.
