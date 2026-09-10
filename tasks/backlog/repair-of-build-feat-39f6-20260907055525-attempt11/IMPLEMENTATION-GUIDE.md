# Repair of build-FEAT-39F6-20260907055525-attempt11 Implementation Guide

## Overview

This guide details the execution strategy for all 4 tasks, including which implementation method to use and how to parallelize work using Conductor workspaces.

## Implementation Method Legend

| Method | Description | When to Use |
|--------|-------------|-------------|
| `/task-work` | Full GuardKit workflow with quality gates | Complex code changes requiring tests, review |
| `Direct` | Direct Claude Code implementation | Scripts, simple changes, documentation |
| `Manual` | Human execution with script | Bulk operations, running scripts |

## Conductor Parallel Execution

Conductor.build enables parallel development via git worktrees. Tasks marked **PARALLEL** can run simultaneously in separate workspaces.

### Workspace Strategy

```
Main Repo (your-repo)
├── Worktree 1: Wave 1 (TASK-ROBF-001, TASK-ROBF-002, TASK-ROBF-004)
├── Worktree 2: Wave 2 (TASK-ROBF-003)
```


---

## Wave 1

**Duration**: 3.0 days
**Workspaces**: 3

### TASK-ROBF-001: Add `timezone=True` to the `deleted_at` column in `src/users/models.py` (line 66: change `DateTime` to `DateTime(timezone=True)`) and update the Alembic migration `alembic/versions/39f6_add_deleted_at_column_to_users.py` (line 35: change `sa.DateTime()` to `sa.DateTime(timezone=True)`) so PostgreSQL stores `TIMESTAMP WITH TIME ZONE` and accepts the timezone-aware `datetime.now(UTC)` values written by `crud.delete_user()`.
| Attribute | Value |
|-----------|-------|
| **Method** | /task-work |
| **Complexity** | 5/10 |
| **Effort** | 1.0 days |
| **Parallel** | **YES** |

**Why /task-work**: Full GuardKit workflow with quality gates (architecture review, tests, code review).

**Execution**:
```bash
/task-work TASK-ROBF-001
```

---
### TASK-ROBF-002: Add try/except around `db.flush()` and `await db.commit()` in `src/users/crud.py` `delete_user()` (lines 161–163) to catch `SQLAlchemyError`, log it, and either retry or return a meaningful error — matching the error-handling pattern used in `create_user()` (lines 38–45).
| Attribute | Value |
|-----------|-------|
| **Method** | /task-work |
| **Complexity** | 5/10 |
| **Effort** | 1.0 days |
| **Parallel** | **YES** |

**Why /task-work**: Full GuardKit workflow with quality gates (architecture review, tests, code review).

**Execution**:
```bash
/task-work TASK-ROBF-002
```

---
### TASK-ROBF-004: Correct the task description in `TASK-FEAT39F6FIX1-repair.md` to reference `DELETE /users/by-email` instead of `DELETE /users/{id}` to accurately reflect the failing endpoint.
| Attribute | Value |
|-----------|-------|
| **Method** | /task-work |
| **Complexity** | 5/10 |
| **Effort** | 1.0 days |
| **Parallel** | **YES** |

**Why /task-work**: Full GuardKit workflow with quality gates (architecture review, tests, code review).

**Execution**:
```bash
/task-work TASK-ROBF-004
```

---

## Wave 2

**Duration**: 1.0 days
**Workspaces**: 1

### TASK-ROBF-003: Add `.where(User.deleted_at.is_(None))` to the query in `src/users/crud.py` `get_user_by_email()` (line 100) so deleted users are excluded, matching the filter used in `get_user()` and `get_users()`.
| Attribute | Value |
|-----------|-------|
| **Method** | /task-work |
| **Complexity** | 5/10 |
| **Effort** | 1.0 days |
| **Parallel** | No |

**Why /task-work**: Full GuardKit workflow with quality gates (architecture review, tests, code review).

**Execution**:
```bash
/task-work TASK-ROBF-003
```

---

## Summary: Task Matrix

| Task | Method | Complexity | Effort | Can Parallel |
|------|--------|------------|--------|--------------|
| TASK-ROBF-001 | /task-work | 5 | 1.0d | **YES** |
| TASK-ROBF-002 | /task-work | 5 | 1.0d | **YES** |
| TASK-ROBF-003 | /task-work | 5 | 1.0d | No |
| TASK-ROBF-004 | /task-work | 5 | 1.0d | **YES** |


## Method Breakdown

| Method | Task Count | Total Effort |
|--------|------------|--------------|
| /task-work | 4 tasks | 4.0 days |


## Recommended Execution Order

```
Wave 1: TASK-ROBF-001, TASK-ROBF-002, TASK-ROBF-004 (PARALLEL)
Wave 2: TASK-ROBF-003
```
