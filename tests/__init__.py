"""The test package — and the first thing that happens in any test run.

WHY THERE IS CODE IN HERE AT ALL. Which database the tests use has to be
settled before anything imports the application, because the application reads
its settings once, at import, and keeps them. A pytest hook runs too late: by
the time ``pytest_configure`` fires, ``tests/conftest.py`` has already imported
``src.main``, and the application has already decided where its database is.

Python imports this file before it imports anything else in the package,
``tests/conftest.py`` included. So this is the earliest place the decision can
be made, and it is made here.

Nothing is raised from here. A failure is remembered and turned into a plain
refusal by ``pytest_configure`` in ``tests/conftest.py``, so a person sees one
sentence rather than an import traceback.

See ``tests/suite_database.py`` for what is being decided and why it matters.
"""

from __future__ import annotations

from tests.suite_database import NoRealDatabase, settle_the_database_for_this_run

# What this run tests against, in one plain line, for the run's header.
WHAT_THIS_RUN_TESTS_AGAINST: str = ""

# Why no real database could be had, or None when one could.
WHY_THERE_IS_NO_DATABASE: str | None = None

try:
    WHAT_THIS_RUN_TESTS_AGAINST = settle_the_database_for_this_run()
except NoRealDatabase as reason:  # turned into a plain refusal by conftest
    WHY_THERE_IS_NO_DATABASE = str(reason)
    WHAT_THIS_RUN_TESTS_AGAINST = "No database was settled for this run."
