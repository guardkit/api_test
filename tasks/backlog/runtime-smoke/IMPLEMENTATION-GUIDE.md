# Implementation Guide — Runtime smoke: seeded round-trip against a sandboxed deployment

Feature: FEAT-8737 · Parent review: TASK-REV-RSMK · 3 tasks, 2 waves.
Binding spec: docs/runtime-smoke-scope-and-buildplan.md (§3 constraints verbatim). Selected
approach: Option 1 — standalone smoke compose + self-contained pytest oracle + in-network
stdlib probe container.

## Data Flow: Read/Write Paths

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["oracle: seed.sql via docker exec psql\n(marker row into users)"]
        W2["probe: POST /users\n(created row)"]
    end

    subgraph Storage["Storage"]
        S1[("smoke db\n(postgres:16-alpine, tmpfs)")]
    end

    subgraph Reads["Read Paths"]
        R1["probe: GET /users listing\n(sees marker row)"]
        R2["probe: GET /users/{id}\n(read-back equality)"]
        R3["oracle: verdict JSON from probe stdout"]
    end

    W1 -->|"direct SQL"| S1
    W2 -->|"through the running app"| S1
    S1 -->|"through the running app"| R1
    S1 -->|"through the running app"| R2
    R1 --> R3
    R2 --> R3
```

*What to look for: both write paths land in the same real database and BOTH are read back
through the running service — no write is verified by the thing that wrote it. No
disconnected paths.*

## Integration Contracts (sequence)

```mermaid
sequenceDiagram
    participant O as oracle (pytest, host)
    participant D as docker/compose
    participant DB as smoke db
    participant A as app (sandboxed)
    participant P as probe container

    O->>D: ensure image apitest-app:smoke (build on host only if missing)
    O->>D: compose -p apitest-smoke up -d
    D->>A: start (internal-only networks)
    O->>D: poll docker inspect until app healthy (<=120s)
    O->>DB: docker exec psql (seed.sql with __MARKER__ substituted)
    O->>P: docker run --network apitest-smoke_probe (probe.py ro-mounted)
    P->>A: GET /users · POST /users · GET /users/{id} · negative probes
    A->>DB: real reads/writes
    P-->>O: ONE stdout line: verdict JSON
    O->>O: assert pass==true (print verdict as evidence)
    O->>D: finally: compose down -v --remove-orphans
```

*What to look for: every artifact retrieved is passed onward — the verdict JSON is consumed
by the oracle's assertion; nothing is fetched and discarded.*

## Task Dependencies

```mermaid
graph TD
    T1[TASK-SMOKE-001: smoke compose stack] --> T3[TASK-SMOKE-003: round-trip oracle]
    T2[TASK-SMOKE-002: seed + probe] --> T3

    style T1 fill:#cfc,stroke:#090
    style T2 fill:#cfc,stroke:#090
```

*Tasks with green background (wave 1) run in parallel — they touch disjoint files.*

## §4: Integration Contracts

### Contract: SMOKE_COMPOSE_FILE
- **Producer task:** TASK-SMOKE-001
- **Consumer task(s):** TASK-SMOKE-003
- **Artifact type:** compose file (`deploy/docker-compose.smoke.yml`)
- **Format constraint:** standalone (never layered on the base file); project `apitest-smoke`; services `app` (image `apitest-app:smoke`, no `build:`) + `db`; networks `backend`+`probe` both `internal: true`; zero `ports:`; no docker socket mounts
- **Validation method:** Coach greps the file for two `internal: true` networks, the image tag, and the absence of `ports:`/`build:`/`docker.sock`; `docker compose -f ... config` parses cleanly

### Contract: SEED_TEMPLATE
- **Producer task:** TASK-SMOKE-002
- **Consumer task(s):** TASK-SMOKE-003
- **Artifact type:** SQL template (`qa/smoke/seed.sql`)
- **Format constraint:** single INSERT into `users` with explicit id/email/full_name/is_active; literal `__MARKER__` token in email (`seeded-__MARKER__@smoke.local`) and full name — the oracle substitutes it per run
- **Validation method:** Coach verifies the `__MARKER__` token appears in both fields; oracle's seeded-listing check proves it end-to-end

### Contract: PROBE_VERDICT_JSON
- **Producer task:** TASK-SMOKE-002 (`qa/smoke/probe.py`)
- **Consumer task(s):** TASK-SMOKE-003
- **Artifact type:** stdout line from the probe container
- **Format constraint:** exactly one JSON line `{"pass": bool, "marker": str, "checks": [{"id", "pass", "detail"}...]}`; exit 0 iff all checks pass; diagnostics to stderr only
- **Validation method:** the seam test in TASK-SMOKE-002 (single parseable line, contract keys); the oracle parses with `json.loads` and asserts

## Execution strategy

Wave 1 (parallel): TASK-SMOKE-001 (direct) · TASK-SMOKE-002 (task-work).
Wave 2: TASK-SMOKE-003 (task-work) — consumes all three contracts above.
Feature smoke gate (after wave 2): the oracle itself runs end to end — the honest gate is the
deliverable. Coordinator's own done bar (scope §5): the oracle green by the coordinator's own
hand, twice in a row, before merge.
