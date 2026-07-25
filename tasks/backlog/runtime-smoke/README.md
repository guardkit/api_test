# Runtime smoke — seeded round-trip against a sandboxed deployment

The factory's first layer-3 runtime verification surface (R5 feature 1 of the 2026-07-25
review-and-mission program; measurable M3: 0 → 1). Deploy the freshly built app into a
sandboxed throwaway compose stack, seed Postgres with a per-run marker, and verify through
the running service that real data round-trips — plus not-found/conflict/validation probes —
from an in-network stdlib probe container with zero egress.

- Binding spec: `docs/runtime-smoke-scope-and-buildplan.md`
- Gherkin: `features/runtime-smoke/runtime-smoke.feature` (12 scenarios)
- Review: `TASK-REV-RSMK-plan-runtime-smoke.md` (Option 1 selected)
- Guide: `IMPLEMENTATION-GUIDE.md` (diagrams + §4 contracts)

| task | what | wave | mode |
|---|---|---|---|
| TASK-SMOKE-001 | sandboxed smoke compose stack | 1 | direct |
| TASK-SMOKE-002 | seed template + stdlib probe | 1 | task-work |
| TASK-SMOKE-003 | users round-trip oracle | 2 | task-work |

Done means (scope §5): the oracle runs green by the coordinator's OWN hand, twice in a row,
inside 300 seconds, with unconditional teardown — and the review-summary + shadow receipts
are read and reported honestly, including any stub attempt.
