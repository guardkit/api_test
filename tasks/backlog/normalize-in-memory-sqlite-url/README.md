# Normalize In-Memory SQLite URL

**Feature:** FEAT-A804
**Status:** Planned

## Summary

The test `tests/test_conftest_database_url.py::TestTheAddressTheHarnessUses::test_nothing_set_gives_the_in_memory_sqlite_it_always_gave` fails with SQLAlchemy 2.1 because the test harness returns the legacy unencoded in-memory SQLite URL (`sqlite:///:memory:`) instead of the percent-encoded form (`sqlite+aiosqlite:///%3Amemory%3A`) that SQLAlchemy 2.1 produces. This feature normalizes the URL in the test harness so it works with both SQLAlchemy 2.0 and 2.1 without pinning the version.

## Tasks

| Task | Title | Wave | Mode | Complexity |
|------|-------|------|------|------------|
| TASK-A804-001 | Normalize in-memory SQLite URL in test harness | 1 | direct | 3 |

## Files Changed

- `tests/conftest.py` — URL normalization in `configured_database_url()`

## Verification

```bash
.venv/bin/python -m pytest tests/test_conftest_database_url.py -x -q
```

## Specification

- `features/normalize-in-memory-sqlite-url/normalize-in-memory-sqlite-url.feature`