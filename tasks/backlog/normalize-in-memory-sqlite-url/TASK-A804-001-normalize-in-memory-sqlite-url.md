---
id: TASK-A804-001
title: "Normalize in-memory SQLite URL in test harness"
task_type: feature
parent_review: TASK-REV-A804
feature_id: FEAT-A804
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
---

Normalize the in-memory SQLite database URL returned by the test harness so it uses the percent-encoded form `sqlite+aiosqlite:///%3Amemory%3A`, which is compatible with both SQLAlchemy 2.0 and 2.1 without pinning the SQLAlchemy version.

## The words of the request this task serves

> The test tests/test_conftest_database_url.py::TestTheAddressTheHarnessUses::test_nothing_set_gives_the_in_memory_sqlite_it_always_gave fails with SQLAlchemy 2.1, which writes the in-memory database address as sqlite+aiosqlite:///%3Amemory%3A. Make it pass with both SQLAlchemy 2.0 and 2.1, without pinning SQLAlchemy.

## Files to Create

- _none_

## Files to Modify

- `tests/conftest.py`

## Acceptance Criteria

- [ ] When no `DATABASE_URL` is set in the environment, `configured_database_url()` in `tests/conftest.py` returns `sqlite+aiosqlite:///%3Amemory%3A` (the percent-encoded in-memory SQLite URL).
- [ ] The returned URL is NOT `sqlite:///:memory:` (the legacy unencoded format).
- [ ] The returned URL is compatible with SQLAlchemy 2.0 (i.e., `sqlalchemy.engine.make_url()` accepts it and produces a valid in-memory SQLite engine).
- [ ] The returned URL is compatible with SQLAlchemy 2.1 (i.e., `sqlalchemy.engine.make_url()` accepts it and produces a valid in-memory SQLite engine).
- [ ] The existing test `tests/test_conftest_database_url.py::TestTheAddressTheHarnessUses::test_nothing_set_gives_the_in_memory_sqlite_it_always_gave` passes with both SQLAlchemy 2.0 and 2.1.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Implementation Notes

- The URL normalization logic lives in `tests/conftest.py`, in or near the `configured_database_url()` function (evidence shows it at lines ~99-120). Locate where the in-memory SQLite fallback URL is constructed and change it from `sqlite:///:memory:` (or `sqlite+aiosqlite:///:memory:`) to `sqlite+aiosqlite:///%3Amemory%3A`.
- The percent-encoding (`%3A` for `:`) is what SQLAlchemy 2.1 uses when rendering the in-memory SQLite URL. SQLAlchemy 2.0 also accepts this form, so normalizing to it once satisfies both versions.
- Do NOT pin the SQLAlchemy version in `requirements/base.txt` or `requirements/dev.txt`. The fix must work with whatever SQLAlchemy 2.x is installed.
- Check whether `tests/__init__.py` or `tests/suite_database.py` also construct in-memory SQLite URLs; if they do, apply the same normalization there. The evidence shows `tests/suite_database.py` defaults to PostgreSQL, so the in-memory path is likely only in `tests/conftest.py`.
- The test `test_nothing_set_gives_the_in_memory_sqlite_it_always_gave` is at `tests/test_conftest_database_url.py:48` (with 1 more hit not shown). Read it to understand exactly what it asserts, then ensure the harness code satisfies it.
- Run the focused test to verify: `.venv/bin/python -m pytest tests/test_conftest_database_url.py -x -q`
- If the test asserts the exact string `sqlite+aiosqlite:///%3Amemory%3A`, the fix is a one-line change in the URL construction. If it asserts compatibility via `make_url()`, ensure the URL round-trips correctly.