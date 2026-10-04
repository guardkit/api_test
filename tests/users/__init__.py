"""Tests for the users feature.

``test_deactivate.py`` is the endpoint-level account of the deactivation
feature (FEAT-2FDE): it asks ``PATCH /users/{user_id}/deactivate`` over HTTP
what its five scenarios promise, and leaves the layers underneath to
``test_deactivate_user.py`` and ``test_deactivate_crud.py``.
"""

from __future__ import annotations
