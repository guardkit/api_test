# Implementation Guide: ETag Generation and Validation

## Overview

This feature adds ETag support to the User API, enabling conditional GET requests. The ETag is a strong validator based on a hash of the user resource body.

## Data Flow: Read/Write Paths

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["User API: update_user()"]
        W2["User API: create_user()"]
    end

    subgraph Storage["Storage"]
        S1[("user_database\n(relational)")]
    end

    subgraph Reads["Read Paths"]
        R1["GET /users/{user_id}"]
        R2["GET /users/{user_id} (with If-None-Match)"]
    end

    W1 -->|"updates"| S1
    W2 -->|"creates"| S1

    S1 -->|"fetches"| R1
    S1 -->|"fetches"| R2

    R2 -.->|"NOT WIRED"| R1
```

**Disconnection Alert**: The read path for conditional GETs (R2) is not explicitly wired to the write path (W1/W2) in this diagram — this is intentional as the middleware handles the conditional logic, but ensures that any update to the user resource invalidates the ETag.

## Integration Contracts

### Contract: ETag header
- **Producer task:** TASK-E613-001
- **Consumer task(s):** TASK-E613-002, TASK-E613-003
- **Artifact type:** HTTP header
- **Format constraint:** Double-quoted hash string (e.g., `"sha256-..."`)
- **Validation method:** Coach verifies ETag header presence and format in response

## Task Dependencies

```mermaid
graph TD
    T1[TASK-E613-001: ETag generation] --> T2[TASK-E613-002: Middleware]
    T2 --> T3[TASK-E613-003: Endpoint update]
    T3 --> T4[TASK-E613-004: Acceptance tests]
    T4 --> T5[TASK-E613-005: Documentation]

    style T1 fill:#cfc,stroke:#090
    style T2 fill:#cfc,stroke:#090
    style T3 fill:#cfc,stroke:#090
    style T4 fill:#cfc,stroke:#090
    style T5 fill:#cfc,stroke:#090
```

_Tasks with green background can run in parallel._

## Execution Strategy

Wave 1: TASK-E613-001 (foundation)
Wave 2: TASK-E613-002 (middleware)
Wave 3: TASK-E613-003 (endpoint update)
Wave 4: TASK-E613-004 (tests)
Wave 5: TASK-E613-005 (documentation)

All tasks are sequential due to dependency chain.

## Implementation Notes

- ETag is a strong validator — use a hash of the full resource body
- Middleware should be reusable across endpoints
- Ensure concurrent requests with same ETag both return 304
- Document ETag behavior in API reference