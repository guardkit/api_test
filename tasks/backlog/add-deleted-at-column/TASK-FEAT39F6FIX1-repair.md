---
id: TASK-FEAT39F6FIX1
title: Repair of build-FEAT-39F6-20260907055525-attempt7
task_type: fix
parent_review: TASK-REV-39F6
feature_id: FEAT-39F6
wave: 1
implementation_mode: task-work
complexity: 3
dependencies: []
---

# Repair of build-FEAT-39F6-20260907055525-attempt7

Repair of build-FEAT-39F6-20260907055525: after the merge, the candidate check in the Docker Sandbox failed 2 of 62 checks on a fresh Postgres — DELETE /users/{id} answered 503 where 204 was expected, in the Hurl twins delete-existing-user (line 40) and double-delete-honest-404 (line 35); the other 60 checks passed. The delete path this feature added works on the SQLite the tests use and fails on Postgres. Gate evidence: qa/gates/evidence/FEAT-39F6-local-20260907T083219Z/EVIDENCE.yaml in the api_test checkout; the merge report: forge receipts merge-build-FEAT-39F6-20260907055525/merge_deploy_report.json.

## What was observed

- Source build: build-FEAT-39F6-20260907055525-attempt7 (feature FEAT-39F6)
- Checks: 60 of 62 passed
- These checks failed:
  - hurl-twins::delete-existing-user::40: expected HTTP 204, observed actual value is <503>
  - hurl-twins::double-delete-honest-404::35: expected HTTP 204, observed actual value is <503>

## Where the evidence is

- Merge report: none was found under the receipts root
- Gate evidence: qa/gates/evidence/FEAT-39F6-local-20260907T083219Z/EVIDENCE.yaml
- Failure pack: none was recorded for this build

## Acceptance Criteria

- [ ] The failed checks pass: hurl-twins::delete-existing-user::40, hurl-twins::double-delete-honest-404::35
- [ ] The feature's existing tests stay green

## Implementation Notes

- Read the evidence named above before changing code.
- This task and its YAML are committed on the branch repair/TASK-FEAT39F6FIX1, cut from main; the fix journey's own branch is cut from there, so both files are in its worktree.
