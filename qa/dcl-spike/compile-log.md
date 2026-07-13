# Compile log — capability.dcl (DCL SPIKE, S2)

Verbatim record of every compile iteration while authoring `capability.dcl` for `/stats`
(TASK-STAT-001). The checker is the S1-staged Go-free WASM harness
`fleet-evals/spike/dcl-authoring/bin/dcl-check.mjs` (vendored from
`github.com/russelleast/Capability-Language` @ `4f9fbe56`, Apache-2.0). This log **is** the
spike's spec-coherence-value evidence: what a compiler catches on a hand-authored spec that
nothing checks on a hand-authored Gherkin file.

- **Author-and-compile-to-green wall time:** 2 min 35 s (start `2026-07-13T13:11:42Z`,
  green at `2026-07-13T13:14:17Z`). This is the write→compile→fix→green loop with the
  planning inputs and the DCL language reference already in hand — the fair comparison
  point against a Gherkin author who likewise already has the inputs and knows Gherkin.
  It does **not** include the one-time cost of learning DCL (a first-time author pays that
  once; see the head-to-head caveat in the results section).
- **Iterations to green:** 2.
- **Checker invocation (reproduce):**
  `node dcl-check.mjs /…/api_test/qa/dcl-spike/capability.dcl` → JSON envelope on stdout,
  exit 0 when `ok:true`, exit 1 when `ok:false`.

---

## Iteration 1 — `ok:false`, exit 1 — 10 errors (root cause: 1)

**What I wrote that triggered it:** the response event field
`firstRequestAt: Text optional` — I reached for an `optional` field qualifier to capture
"`first_request_at` is null until the service has handled its first request."

**Verbatim checker output:**

```json
{
  "ok": false,
  "diagnostics": [
    { "severity": "error", "message": "expected :",   "code": "DCL_PARSE_EXPECTED_TOKEN",      "line": 30, "column": 32 },
    { "severity": "error", "message": "expected type", "code": "DCL_PARSE_EXPECTED_IDENTIFIER", "line": 31, "column": 1  },
    { "severity": "error", "message": "expected :",   "code": "DCL_PARSE_EXPECTED_TOKEN",      "line": 36, "column": 8  },
    { "severity": "error", "message": "expected type", "code": "DCL_PARSE_EXPECTED_IDENTIFIER", "line": 36, "column": 31 },
    { "severity": "error", "message": "expected :",   "code": "DCL_PARSE_EXPECTED_TOKEN",      "line": 37, "column": 16 },
    { "severity": "error", "message": "expected type", "code": "DCL_PARSE_EXPECTED_IDENTIFIER", "line": 37, "column": 17 },
    { "severity": "error", "message": "expected :",   "code": "DCL_PARSE_EXPECTED_TOKEN",      "line": 38, "column": 26 },
    { "severity": "error", "message": "expected type", "code": "DCL_PARSE_EXPECTED_IDENTIFIER", "line": 38, "column": 33 },
    { "severity": "error", "message": "unexpected }",  "code": "DCL_PARSE_UNEXPECTED_TOKEN",     "line": 40, "column": 1  },
    { "severity": "error", "message": "undefined policy", "code": "DCL_SEM_UNKNOWN_POLICY",     "line": 52, "column": 5  }
  ],
  "diagnosticCount": 10, "errorCount": 10, "warningCount": 0, "infoCount": 0, "sourceCount": 1
}
```

**What the compiler caught (honest reading):** ONE real defect that cascaded into 10
diagnostics. DCL v1.0 has **no `optional`/nullable field qualifier** — shape/event fields are
`required`-only (confirmed: `optional` appears in zero `.dcl` files across the pinned repo;
`required` is the only qualifier, used 175×). The parser read `optional` as the *next field
name*, expected a `:` after it (col 32 error), and the desync then mis-parsed the rest of the
event shape, swallowed the closing `}`, and — because the `policy` block never registered —
finally reported `DCL_SEM_UNKNOWN_POLICY` where the capability referenced it (line 52).

**Classification:** this is a **language-conformance** catch (an invalid token), not a deep
semantic-modeling inconsistency (undefined actor, uncaused outcome, unreachable lifecycle
state — the classes §2 PROBE-2 exercised). It is still a genuine machine catch with an exact
line/column that a Gherkin file has **no equivalent for** (nothing validates a `.feature`'s
internal well-formedness), but honesty requires naming it as a syntax catch on a simple spec,
not evidence that DCL surfaced a hidden requirement ambiguity.

**Fix:** `firstRequestAt: Text required`. The field is always *present* in the response body
(its *value* may be `null`); DCL cannot express the value-nullability, so that nuance moves to
the pass-bar / scenarios. One-line change.

---

## Iteration 2 — `ok:true`, exit 0 — clean

**Verbatim checker output:**

```json
{
  "ok": true,
  "diagnostics": [],
  "diagnosticCount": 0,
  "errorCount": 0,
  "warningCount": 0,
  "infoCount": 0,
  "sourceCount": 1
}
```

Compile gate GREEN. Zero errors, zero warnings.

**Also silently accepted (worth recording — each is a small coherence check that passed):**

- **Empty intent shape** `shape StatisticsQuery { }` — a GET with no request body is
  representable; the compiler did not require a field.
- **Availability policy** `availability { dependency_tolerance allowed }` governing the
  capability — accepted; this is the "stays available when the DB is down" guarantee.
- **Lifecycle** `begin Fresh → step Fresh → end Serving` with
  `move Fresh to Serving on outcome StatisticsReported` — accepted with **no** unreachable-
  state or ambiguous-transition warning (the classes pressure-tests 17/18 raise). The
  single-outcome `when { always StatisticsReported }` drove no redundant-policy warning
  either (unlike the README example's 4× `DCL_SEM_REDUNDANT_POLICY`).

---

## Bottom line for the head-to-head

- **Compiler value, honestly stated:** it *did* catch a real error the first pass
  (`optional` is not in the language) with precise line/column and machine-readable codes —
  a check with **no Gherkin analogue**. But on a spec this simple it was a *conformance*
  catch, not a *requirement-coherence* catch; it did not surface a hidden `/stats` ambiguity
  that the spec/coach/human would have missed. The deeper semantic checks (undefined refs,
  uncaused outcomes, unreachable lifecycle) had nothing to bite on here because the modeled
  spec is small and internally consistent.
- **What DCL could NOT express** (carried out of this log into the results table): the
  integer-ness of `requests_served` (only `Number` exists), the value-nullability of
  `first_request_at`, the monotonic-counter invariant, the POST-405 read-only rejection at
  the HTTP layer, and the restart-resets-count behaviour — none have a first-class DCL home;
  DCL models the *capability's responsibilities*, not HTTP verbs or temporal invariants.
