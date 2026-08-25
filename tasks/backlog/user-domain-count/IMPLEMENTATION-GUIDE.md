# Implementation Guide: User Domain Count API

## Overview

This feature implements a GET /users/count-by-domain endpoint that returns the number of users grouped by email domain, ordered by count descending.

## Data Flow

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["user_service.get_users()"]
    end

    subgraph Storage["Storage"]
        S1[("user_db")]
    end

    subgraph Reads["Read Paths"]
        R1["GET /users/count-by-domain"]
        R2["reporting_service.get_domain_stats()"]
    end

    W1 -->|"fetches"| S1
    S1 -->|"returns users"| R1
    S1 -->|"returns users"| R2

    R2 -.->|"NOT WIRED"| R1
```
*Note: R2 is a future integration point for reporting services.*

## Integration Contracts

### Contract: domain_count_endpoint
- **Producer task:** TASK-7CEA-001
- **Consumer task(s):** TASK-7CEA-003, TASK-7CEA-005
- **Artifact type:** HTTP response
- **Format constraint:** JSON array of {domain: string, count: number}
- **Validation method:** Hurl tests validating status code and JSON structure

## Task Dependencies

```mermaid
graph TD
    T1[TASK-7CEA-001: Create endpoint] --> T2[TASK-7CEA-002: Implement extraction]
    T2 --> T3[TASK-7CEA-003: Add tests]
    T3 --> T4[TASK-7CEA-004: Add documentation]
    T4 --> T5[TASK-7CEA-005: Verify smoke test]

    style T1 fill:#cfc,stroke:#090
    style T2 fill:#cfc,stroke:#090
    style T3 fill:#cfc,stroke:#090
    style T4 fill:#cfc,stroke:#090
    style T5 fill:#cfc,stroke:#090
```
*Tasks in green can run in parallel if dependencies are met.*

## Execution Strategy

Wave 1: 1 task
  ⚡ TASK-7CEA-001: Create domain count endpoint (direct)

Wave 2: 1 task
  ⚡ TASK-7CEA-002: Implement domain extraction logic (task-work)

Wave 3: 1 task
  ⚡ TASK-7CEA-003: Add domain count tests (task-work)

Wave 4: 1 task
  ⚡ TASK-7CEA-004: Add documentation (direct)

Wave 5: 1 task
  ⚡ TASK-7CEA-005: Verify endpoint with smoke test (direct)

## Deferred Planning Decisions

| decision point | chosen default | status |
|---|---|---|
| review_focus | all aspects | deferred |
| tradeoff_priority | balanced | deferred |
| approach_selection | recommended | deferred |
| execution_preference | auto-detect | deferred |
| testing_depth | default | deferred |
| mode_boundary_normalization | task-work (>=4) / direct (<4) | deferred |