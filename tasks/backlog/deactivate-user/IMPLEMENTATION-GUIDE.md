# Implementation Guide: Deactivate User Endpoint

This feature implements the user deactivation endpoint.

## Architecture

The feature follows the project's architecture:
- **Router**: `src/users/router.py` declares the endpoint
- **CRUD**: `src/users/crud.py` implements the deactivation logic
- **Schemas**: `src/users/schemas.py` defines the response shape
- **Models**: `src/users/models.py` contains the User model

## Data Flow

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["router.deactivate_user()"]
    end

    subgraph Storage["Storage"]
        S1[("users_table\n(PostgreSQL)")]
    end

    subgraph Reads["Read Paths"]
        R1["router.get_user()"]
        R2["router.list_users()"]
    end

    W1 -->|"update status"| S1
    S1 -->|"select"| R1
    S1 -->|"select"| R2

    style R1 fill:#cfc,stroke:#090
    style R2 fill:#cfc,stroke:#090
```
*All read paths are wired to the write path.*

## §4: Integration Contracts

```markdown
## §4: Integration Contracts

### Contract: user_deactivation_response
- **Producer task:** TASK-2FDE-001
- **Consumer task(s):** TASK-2FDE-003
- **Artifact type:** HTTP response body
- **Format constraint:** JSON object containing the updated user with `is_active: false`
- **Validation method:** Hurl test asserting status 200 and `is_active` field
```