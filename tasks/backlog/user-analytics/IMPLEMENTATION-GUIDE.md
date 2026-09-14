# Implementation Guide: User Creation Analytics - Daily Counts

## Overview

This feature implements a new analytics endpoint that provides a 7-day rolling window of user creation counts.

## Architecture

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["User creation event"]
    end

    subgraph Storage["Storage"]
        S1[("users table\n(PostgreSQL)")]
    end

    subgraph Reads["Read Paths"]
        R1["GET /users/created-per-day"]
    end

    W1 -->|"inserts"| S1
    S1 -->|"query"| R1

    style R1 fill:#cfc,stroke:#090
```
*Data flow: User creation writes to the users table, which is then queried by the analytics endpoint.*

## Integration Contracts

### Contract: user_creation_counts
- **Producer task:** TASK-6F3D-002
- **Consumer task(s):** TASK-6F3D-003
- **Artifact type:** Pydantic schema (List[UserCount])
- **Format constraint:** List of objects with 'date' (ISO-8601) and 'count' (non-negative int) keys
- **Validation method:** Coach verifies response schema matches Pydantic model

## Task Dependencies

```mermaid
graph TD
    T1[TASK-6F3D-001: Schema] --> T2[TASK-6F3D-002: CRUD]
    T2 --> T3[TASK-6F3D-003: Router]
    T3 --> T4[TASK-6F3D-004: Service]
    T4 --> T5[TASK-6F3D-005: Tests]

    style T2 fill:#cfc,stroke:#090
    style T3 fill:#cfc,stroke:#090
    style T4 fill:#cfc,stroke:#090
```
*Tasks with green background can run in parallel if Conductor is used.*

## Implementation Strategy

1. **Data Model**: Add analytics-specific fields or a separate table if needed.
2. **CRUD**: Implement the query logic using SQLAlchemy 2.0.
3. **Router**: Expose the endpoint with appropriate Pydantic schemas.
4. **Service**: Orchestrate the data retrieval and formatting.
5. **Testing**: Add integration tests covering all scenarios from the feature spec.

## Deferred Decisions

| Decision Point | Chosen Default | Status |
|---|---|---|
| Storage approach | Use existing users table with created_at index | deferred |
| Response format | JSON array of objects with date and count | deferred |
| Timezone handling | UTC for all calculations | deferred |