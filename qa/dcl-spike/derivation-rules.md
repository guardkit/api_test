# Derivation rules — DCL capability → outside-in assertions (DCL SPIKE, S3)

**What this is.** The *general* mapping rules that turn a compiled DCL capability into a set of
outside-in conformance assertions run against the RUNNING service. These rules are the spike's
**mechanizability evidence**: the re-aimed pass/kill (`dcl-factory-evaluation-2026-07.md` §7) asks
whether assertions can be *derived from the DCL by recorded, systematic rules* rather than
hand-glued per stack. So this file is written as the spec a tool would implement — block-shape in,
assertion-template out — and every place where a **rule alone is not enough** and human judgment had
to supply information the DCL does not carry is flagged `[Jn]`. The judgment-flag count is as much
the result as the rule count: the more `[Jn]`, the less mechanizable the path.

**Input contract.** The rules consume the DCL capability's compiled blocks (the `dcl compile`/`ir`
surface): `intent`, `outcome`, `rule`, `effect`, `event` (+ the `emits` list and each event's typed
fields), `policy` (+ its policy-kind body), `observe` (the named metrics), `when`, and `lifecycle`
(states + `move … on …` transitions). For this spike the blocks are read directly from the authored
`capability.dcl` (the vendored WASM harness emits the diagnostic envelope only, not the IR JSON — an
honest tooling limit noted in S1; a production path would use the real `dcl ir --json`).

**Output contract.** A list of assertions, each carrying: an id, the DCL block it derives from
(citation), the general rule that produced it (`Rn`), the judgment flags it needed (`[Jn]`), and a
runnable predicate over an HTTP response (or a `SKIP`/`MISS` disposition with a recorded reason).

---

## The general rules (block → assertion template)

> Read "the capability's invocation surface" = the concrete request the `intent` maps to. Read
> "success signal" / "observable output" = the HTTP response the running service returns.

- **R1 · `intent Shape from Actor` → invocation surface.** The `intent` names the request that
  drives the capability. Derive the invocation used by every other assertion: method + path +
  (if the intent `shape` has fields) a request body carrying those fields. An **empty shape** →
  a no-body request. *Judgment:* the DCL carries no transport binding — `[J1]`.

- **R2 · `outcome X` (reachable via `when`/`lifecycle`) → success assertion.** Each declared
  success `outcome` that the `when`/`lifecycle` blocks can reach → one assertion that invoking the
  intent yields the success signal. *Judgment:* "success signal = HTTP 200" is not in the DCL —
  `[J2]`.

- **R3 · `event E is { f: T … }` referenced by `emits` → one field assertion per field.** For each
  typed field `f: T` of an emitted event, derive: (a) `f` is **present** in the observable output;
  (b) its value **conforms to `T`** (`Text`→string, `Number`→numeric, `Flag`→boolean, a `shape`
  ref→object). *Judgment:* field-name case/whitespace mapping DCL-identifier→wire-key `[J3]`;
  `Number`→integer narrowing is **not** derivable (DCL `Number` ⊇ float) `[J4]`; `Text`→a specific
  string format (ISO-8601, email, …) is **not** derivable `[J5]`; a `required` field's **value**
  may still be null on the wire — `required` constrains presence, not nullability `[J6]`.

- **R4 · `observe … count as M` → monotone-metric assertion.** A `count` observation names a
  running tally. Derive: invoke the intent twice; the wire quantity backing `M` does not go
  **down** between calls. *Judgment:* the DCL says a count *exists*, not that it is **strictly**
  increasing nor that a given wire field *is* that count — `[J7]`.

- **R5 · `observe capability duration as M` → liveness/latency probe.** A `duration` observation →
  the intent returns within a bounded time (a smoke/liveness probe). *Judgment:* the DCL states no
  bound — `[J7]` (same family: the metric is named, the threshold is not).

- **R6 · `lifecycle { move A to B on outcome O }` → post-transition state assertion.** Each
  transition → exercise its trigger (produce `O` by invoking the intent) then assert the
  **destination-state observable** holds. Which wire fact *is* the destination-state observable is
  read from the state's modeled meaning. *Judgment:* the observable binding for a state is not in
  the DCL — `[J6]`/`[J1]`.

- **R7 · `lifecycle { end S }` (terminal state) → stability assertion.** A terminal state that is
  reached-and-stays → the facts that define it do not change across repeated observation once
  entered. *Judgment:* "stable/immutable once set" is read *into* the terminal state; DCL marks it
  terminal, not immutable — `[J9]`.

- **R8 · `policy P { availability { dependency_tolerance allowed } } governs capability` →
  degraded-dependency assertion.** An availability policy tolerating a down dependency → with that
  dependency unavailable, the intent still yields its success signal. *Judgment:* the DCL names
  **no concrete dependency** and **no fault-injection surface**, so the assertion is derivable in
  shape but its execution needs an out-of-band way to take a specific dependency down — `[J8]`.

- **R9 · `rule R { … }` → precondition + negative-case assertions.** Each `rule` (a guard/constraint
  on the capability) → (a) a positive assertion that a conforming request is accepted; (b) a
  **negative** assertion that a violating request is rejected. *Judgment:* how a violation is
  expressed on the wire (which status/verb) is not in the DCL — `[J1]`. **NB for this capability:**
  `capability.dcl` declares **no `rule` block**, so R9 fires zero assertions here — which is exactly
  why the read-only/mutation-rejection check has no DCL source to derive from (see coverage
  cross-check; this is a finding, not an omission of the rules).

---

## The judgment flags (what a rule could not supply on its own)

Every `[Jn]` is a fact the assertion needs that the **DCL does not carry** — i.e. a place where a
purely mechanical deriver would stall and a human (or an external binding file) had to fill in. The
honest reading: R1–R9 are mechanical *given* a small, fixed binding table (J1–J3 are the same three
facts reused everywhere); J4–J9 are genuine expressiveness gaps in DCL v1.0 for a wire/HTTP target.

| Flag | What judgment had to supply | Why the DCL can't | Mechanizable by a binding table? |
|---|---|---|---|
| **J1** | capability → `GET /stats` (verb + path) | DCL has no transport binding | **Yes** — one line in a binding file |
| **J2** | success outcome → HTTP `200` | outcome carries no status code | **Yes** — one binding line |
| **J3** | `requestsServed` → wire key `requests_served` (case map) | identifier style ≠ wire style | **Yes** — a naming convention (camel→snake) |
| **J4** | `requestsServed` is an **integer**, not any number | DCL `Number` ⊇ float | **No** — DCL v1.0 lacks an integer type |
| **J5** | `firstRequestAt` is **UTC ISO-8601** | DCL `Text` carries no format | **No** — DCL v1.0 lacks a format constraint |
| **J6** | `firstRequestAt` **value** may be null pre-first-request | `required` = present, not non-null | **No** — DCL v1.0 has no nullable qualifier |
| **J7** | `requests_served` **strictly** increases / is the count | `count` = a tally exists, not monotone-strict | **Partly** — a "counter" stereotype could |
| **J8** | the down dependency = the **database**; how to fault-inject it | policy names no dependency, no fault surface | **No** — needs an external dependency map + a harness |
| **J9** | `first_request_at` is **immutable once set** | terminal state ≠ immutable fact | **No** — DCL v1.0 has no immutability qualifier |

**Count:** **9 general rules** (R1–R9), **9 judgment flags** (J1–J9). Of the 9 flags, **3 (J1–J3)**
are a fixed binding table reusable across any HTTP capability; **6 (J4–J9)** are DCL v1.0
expressiveness gaps against a wire/HTTP verification target. That 6 is the honest cost the head-to-head
must weigh: they are the reasons the derived set cannot, from the DCL alone, pin integer-ness, a date
format, null-until-first, strict monotonicity, dependency-down behaviour, or immutability.

---

## The derived assertion set (mechanical application of R1–R9 to `capability.dcl`)

Applying the rules to the authored blocks, in order. Each row cites its DCL source line(s).

| Id | Rule | DCL source (capability.dcl) | Assertion | Flags | Disposition |
|---|---|---|---|---|---|
| **A-INTENT** | R1 | `intent StatisticsQuery from Operator` (l.45) + empty `shape StatisticsQuery {}` (l.21) | invoke `GET /stats`, no body | J1 | (surface for all below) |
| **A-OUTCOME** | R2 | `outcome StatisticsReported` (l.47); `when { always StatisticsReported }` (l.63–65) | `GET /stats` → HTTP 200 | J1,J2 | RUN |
| **A-FIELD-SVC** | R3 | `event StatisticsProduced … service: Text required` (l.29–30) | body has `service`, a non-empty string | J1,J3 | RUN |
| **A-FIELD-REQ** | R3 | `… requestsServed: Number required` (l.31) | body has `requests_served`, numeric | J1,J3,J4 | RUN |
| **A-FIELD-FRA** | R3 | `… firstRequestAt: Text required` (l.32) | body has `first_request_at` (present) | J1,J3,J6 | RUN |
| **A-COUNT-MONO** | R4 | `observe … event StatisticsProduced count as statistics_reports` (l.59) + `outcome … count` (l.60) | two calls → `requests_served` does not decrease | J1,J7 | RUN |
| **A-DURATION** | R5 | `observe capability duration as stats_report_duration` (l.58) | `GET /stats` returns < 5 s | J1,J7 | RUN |
| **A-LIFE-SERVING** | R6 | `lifecycle { move Fresh to Serving on outcome StatisticsReported }` (l.74) | after a request, `first_request_at` is non-null (Serving-state observable) | J1,J6 | RUN |
| **A-LIFE-STABLE** | R7 | `lifecycle { end Serving }` (l.73) | two calls → `first_request_at` identical | J1,J9 | RUN |
| **A-FRA-FORMAT** | R3+[J5] | `firstRequestAt: Text required` (l.32) — format is **judgment-sourced, not DCL** | `first_request_at` parses as UTC ISO-8601 | J1,J3,J5 | RUN (flagged: not pure-DCL) |
| **A-AVAIL** | R8 | `policy StatisticsAvailability { availability { dependency_tolerance allowed } }` (l.38–42, `governs capability` l.54) | with the DB down, `GET /stats` → 200 | J1,J8 | **SKIP** — needs DB fault-injection; out of the read-only HTTP venue. Recorded, not run. |
| **A-READONLY** | R9 | *(no `rule` block exists)* | *(would be: `POST /stats` → 405)* | — | **MISS** — no DCL construct to derive from. The flagship coverage gap. |

**Runnable:** 9 (A-OUTCOME … A-FRA-FORMAT). **Derived-but-not-runnable:** 1 (A-AVAIL, SKIP with
reason). **Not-derivable:** 1 (A-READONLY, MISS — the DCL as authored carries no rule for it).
A-INTENT is the shared invocation surface, not a standalone pass/fail. Total assertion *concepts*
produced by the rules = 11 (9 RUN + 1 SKIP + 1 MISS).

---

## R10 — the closed-world binding rule (added 2026-07-13 late evening: the Path-1 condition discharge)

*Context: Rich's attended V-02 verdict on the spike was **PASS, conditional on Path 1** — closing
the A-READONLY MISS at the RULES level, without waiting on a DCL language change. This section is
that discharge; the re-run receipt is in `RUN-RECEIPT.md`'s dated addendum.*

- **R10 · closed-world over the declared intent set → rejection assertions.** The J1 binding table
  maps each declared `intent` to a verb+path. R10 adds ONE convention on top: **any HTTP verb with
  mutation semantics (`POST`/`PUT`/`PATCH`/`DELETE`) on a bound path that is NOT derived from any
  declared intent is asserted to be REJECTED (4xx; 405 where the service distinguishes).** What is
  not declared is forbidden — the same closed-world reading a compiler gives an enum.
  *Judgment:* none new — R10 consumes only the J1 table plus the fixed mutating-verb list; it is a
  rule written ONCE that applies to every capability, never per-feature glue (the pass/kill
  discipline: fixes live at the rules level or they are step-definitions reborn).
  *Placement note:* this deliberately lives in the BINDING layer, not the language — "which verbs
  exist" is a transport concern, and DCL stays implementation-agnostic (consistent with the
  language's own design posture). A first-class DCL prohibition construct (Path 2) remains
  Russell's roadmap call and would also serve non-HTTP targets.

**R10 applied to `capability.dcl`:** only `GET` derives from `intent StatisticsQuery` (l.45) →
four derived assertions **A-CW-POST / A-CW-PUT / A-CW-PATCH / A-CW-DELETE** (each: verb on
`/stats` → 4xx). **Live result 2026-07-13: 4/4 PASS (all HTTP 405)** — the run moves to
**13/13 RUN PASS**; A-READONLY's R9 row is kept above as the honest pre-R10 record. Count: **10
general rules**, judgment flags unchanged (no new judgment was needed — the strongest possible
mechanizability signal for the closure).
