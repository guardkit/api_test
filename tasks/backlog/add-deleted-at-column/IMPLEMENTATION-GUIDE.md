# Implementation Guide: Add deleted_at column to users table

This feature implements soft-delete support for the users table by adding a nullable `deleted_at` timestamp column.

## Architecture

The following diagram shows the data flow for this feature.

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["POST /users (create)"]
        W2["PATCH /users/{id} (soft-delete)"]
    end

    subgraph Storage["Storage"]
        S1[("users table\n(PostgreSQL)")]
    end

    subgraph Reads["Read Paths"]
        R1["GET /users (list)"]
        R2["GET /users/count-by-domain"]
    end

    W1 -->|"INSERT"| S1
    W2 -->|"UPDATE deleted_at"| S1

    S1 -->|"SELECT"| R1
    S1 -->|"SELECT"| R2

    style R1 fill:#cfc,stroke:#090
    style R2 fill:#cfc,stroke:#090
```
*Data flow: Write paths to the users table and corresponding read paths.*

## Integration Contracts

This feature has no cross-task data dependencies.

## Task Dependencies

```mermaid
graph TD
    T1[TASK-39F6-001: Add column] --> T2[TASK-39F6-002: Update model]
    T2 --> T3[TASK-39F6-003: Update CRUD]
    T3 --> T4[TASK-39F6-004: Add tests]

    style T2 fill:#cfc,stroke:#090
    style T3 fill:#cfc,stroke:#090
```
*Tasks with green background can run in parallel.*

## Execution Strategy

Wave 1: 1 task (sequential)
  ⚡ Conductor recommended
     • TASK-39F6-001: Add column (direct, wave1-1)

Wave 2: 1 task (sequential)
  ⚡ Conductor recommended
     • TASK-39F6-002: Update model (direct, wave2-1)

Wave 3: 1 task (sequential)
  ⚡ Conductor recommended
     • TASK-39F6-003: Update CRUD (task-work, wave3-1)

Wave 4: 1 task (sequential)
  ⚡ Conductor recommended
     • TASK-39F6-004: Add tests (task-work, wave4-1)