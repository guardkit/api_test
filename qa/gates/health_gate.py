#!/usr/bin/env python3
"""F4 HEALTH gate — GET /health 200 + database:connected + the two headers.

Registered in qa/gates/registry.yaml as gate id ``health``. Honours the F4
contract via _gatelib (exit 0 = pass; non-zero enumerates failing assertions as
the JSON results envelope). Target base URL comes from $API_TEST_BASE_URL
(default http://localhost:8901).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _gatelib  # noqa: E402

SPEC = {
    "gate_id": "health",
    "base_url_env": "API_TEST_BASE_URL",
    "default_base_url": "http://localhost:8901",
    "request": {"method": "GET", "path": "/health"},
    "expect_status": 200,
    "headers_present": ["x-correlation-id", "x-api-version"],
    "json_assertions": [
        {"id": "health::db_connected", "path": "database", "equals": "connected"},
    ],
}

if __name__ == "__main__":
    _gatelib.run_spec(SPEC)
