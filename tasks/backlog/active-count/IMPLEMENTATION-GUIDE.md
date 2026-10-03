# Implementation Guide: Active Count Endpoint

This feature implements a read-only endpoint to monitor user activity by returning counts of active and inactive users.

## Architecture

The endpoint follows the project's feature-based module structure.

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["User creation (existing)"]
    end

    subgraph Storage["Storage"]
        S1[("users table\n(PostgreSQL)")]
    end

    subgraph Reads["Read Paths"]
        R1["GET /users/active-count\n(active_count, inactive_count)"]
    end

    W1 -->|"inserts"| S1
    S1 -->|"query"| R1

    style R1 fill:#cfc,stroke:#090
```
*Data flow diagram: Write path from user creation to storage, and read path from storage to the new endpoint.*

## Data Flow: Read/Write Paths

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["User creation (existing)"]
    end

    subgraph Storage["Storage"]
        S1[("users table\n(PostgreSQL)")]
    end

    subgraph Reads["Read Paths"]
        R1["GET /users/active-count\n(active_count, inactive_count)"]
    end

    W1 -->|"inserts"| S1
    S1 -->|"query"| R1

    style R1 fill:#cfc,stroke:#090
```
*Data flow diagram: Write path from user creation to storage, and read path from storage to the new endpoint.*

## §4: Integration Contracts

No cross-task data dependencies identified for this feature. All tasks are independent.