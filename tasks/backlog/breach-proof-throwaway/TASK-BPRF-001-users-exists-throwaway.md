---
complexity: 2
dependencies: []
feature_id: FEAT-BPRF
id: TASK-BPRF-001
implementation_mode: task-work
status: backlog
task_type: feature
title: Add GET /users/exists endpoint (THROWAWAY breach-proof)
wave: 1
---

# Add GET /users/exists endpoint (THROWAWAY — breach-proof run)

**THIS TASK'S OUTPUT IS DELIBERATELY DISCARDED.** It exists so the factory can
watch the UBS-002 `breach-proof` budget profile (wall-clock cap 120s) kill a
real build honestly. The build WILL be terminated by the runner at the cap —
that termination is the success condition of the exercise, not a defect. The
branch is never merged and is swept after the proof.

The (real-shaped) work, for as long as the clock allows: expose
`GET /users/exists?email=<address>` returning `{"exists": true|false}` with
HTTP 200 in both cases. Reuse `crud.get_user_by_email` (src/users/crud.py:79);
`EmailStr` query validation (422 on malformed); declare the literal route
before `GET /users/{user_id}`; 503 naming the database when it is down (the
`/users/count` convention). Tests in tests/users/ per the existing patterns.

## Acceptance Criteria
- [ ] GET /users/exists?email=<existing> returns 200 {"exists": true}
- [ ] GET /users/exists?email=<unknown> returns 200 {"exists": false}
- [ ] A malformed address returns 422 without touching the database
- [ ] GET /users/{user_id} still resolves (route order preserved) and the suite stays green
- [ ] With the database unavailable, the route returns 503 naming the database
