"""ETag generation utilities for HTTP response caching.

Provides deterministic ETag generation based on resource content using
SHA-256 hashing. ETags are returned as strong validators per RFC 9110.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

ETAG_PREFIX = '"'
ETAG_SUFFIX = '"'
HASH_ALGORITHM = "sha256"


def generate_etag(data: Any) -> str:
    """Generate a strong ETag from resource data.

    Serializes the data to a canonical JSON representation, hashes it
    with SHA-256, and wraps the hex digest in double quotes to produce
    a strong ETag per RFC 9110.

    Args:
        data: The resource data to hash. Can be any JSON-serializable
            type (dict, list, str, int, float, bool, None).

    Returns:
        A strong ETag string, e.g. ``"<sha256-hex-digest>"``.

    Raises:
        TypeError: If the data is not JSON-serializable.
    """
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{ETAG_PREFIX}{digest}{ETAG_SUFFIX}"


def etag_matches(etag: str | None, resource_data: Any) -> bool:
    """Check whether a provided ETag matches the current resource state.

    Compares the incoming ETag against the ETag generated from the
    current resource data. Returns True if they match, indicating the
    client's cached copy is still valid.

    Args:
        etag: The ETag sent by the client, or None if absent.
        resource_data: The current resource data to generate a fresh ETag.

    Returns:
        True if the ETags match, False otherwise.
    """
    if etag is None:
        return False
    current_etag = generate_etag(resource_data)
    return etag == current_etag
