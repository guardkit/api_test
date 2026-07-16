# Poison-prove receipt — `dcl-stats` gate (Phase D / D3)

Proves the DCL live gate fails **LOUD** on a wrong expected value (F4 contract:
a wrong assertion must fail, never green, never silent-skip) and recovers when
restored. Method: poison **one** expected value in a *copy* of the derived set
(`qa/dcl/derived/TASK-STAT-001-POISON.yaml` — the committed
`TASK-STAT-001.yaml` is never touched), run the registered `dcl-stats` gate
through `qa/gates/local_live_gate.py`, then delete the copy and re-run.

- **Target:** live compose deploy `apitest-f2` at `http://localhost:8901`
  (read-only HTTP; only GETs + already-405 mutating verbs).
- **Gate path:** `cd guardkit && API_TEST_BASE_URL=http://localhost:8901
  DCL_FEATURE=<set> uv run --no-sync python
  <api_test>/qa/gates/local_live_gate.py --feature FEAT-AE43 --target local
  --gates dcl-stats --repo <api_test>`
- **Poison:** `A-OUTCOME` predicate `expected: 200 -> 999` (in the copy only).

## Three runs

| state   | run_id                              | verdict / exit | gate result |
|---------|-------------------------------------|----------------|-------------|
| clean   | `FEAT-AE43-local-20260716T183934Z`  | pass / 0       | dcl-stats 13 pass / 0 fail |
| poison  | `FEAT-AE43-local-20260716T184026Z`  | fail / 1       | dcl-stats 12 pass / 1 fail |
| restore | `FEAT-AE43-local-20260716T184036Z`  | pass / 0       | dcl-stats 13 pass / 0 fail |

## The loud failure (poison run F4 envelope, the failing assertion named)

```json
{ "id": "A-OUTCOME", "status": "fail", "observed": "200", "expected": "999" }
```

The gate named the exact poisoned assertion (`A-OUTCOME`), reported the real
observed value (`200`) against the poisoned expectation (`999`), and returned a
non-zero verdict — no vacuous green. Restoring the correct set (deleting the
poison copy) returns the gate to 13/13 pass.

## Notes

- The 13 RUN ids (`A-OUTCOME`, `A-FIELD-SVC/REQ/FRA`, `A-COUNT-MONO`,
  `A-DURATION`, `A-LIFE-SERVING`, `A-LIFE-STABLE`, `A-FRA-FORMAT`,
  `A-CW-POST/PUT/PATCH/DELETE`) + 1 SKIP (`A-AVAIL`) reproduce the spike's
  golden set exactly (`qa/dcl-spike/RUN-RECEIPT.md`).
- Per-run F4 envelopes + evidence are the runner's `qa/gates/history/<run_id>.json`
  + `qa/gates/evidence/<run_id>/` (gitignored runtime receipts); this file is
  the committed record of the drill.
