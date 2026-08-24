# API Documentation

## Overview

This document provides detailed information about the API endpoints available in the FastAPI backend template.

**Base URL**: `http://localhost:8000`  
**API Version**: 0.1.0  
**Contact**: support@example.com  
**License**: MIT

## Interactive Documentation

The API provides interactive documentation through:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Endpoints

### Version Information

#### GET /version

Returns the application version information, including the current version, git commit hash, and service name.

**Tags**: `version`

**Authentication**: None required

**Response**: `200 OK`

**Response Schema**:
```json
{
  "version": "string",
  "commit": "string",
  "service": "string"
}
```

**Field Descriptions**:
- `version` (string): Application version string (e.g., "0.1.0")
- `commit` (string): Git commit hash, shortened to 7 characters (e.g., "1b0f90b")
- `service` (string): Service name (e.g., "api")

**Example Request**:
```bash
curl -X GET http://localhost:8000/version
```

**Example Response**:
```json
{
  "version": "0.1.0",
  "commit": "1b0f90b",
  "service": "api"
}
```

**Status Codes**:
- `200 OK`: Version information retrieved successfully
- `405 Method Not Allowed`: HTTP method not allowed (only GET is supported)

**Use Cases**:
- Health monitoring and deployment verification
- Tracking which version is deployed in different environments
- Debugging and troubleshooting to ensure correct version is running
- CI/CD pipeline validation

**Implementation Notes**:
- The version is read from the `app_version` configuration setting
- The commit hash is extracted from the git repository at runtime
- If git information is unavailable, the commit field returns "unknown"
- This endpoint does not require authentication and is publicly accessible

---

### Readiness Check

#### GET /ready

Returns whether the service is ready to accept requests. This endpoint is intended
for Kubernetes readiness probes and load balancer health checks. Returns HTTP 200
when the service is ready and HTTP 503 when the service is not ready.

**Tags**: `health`

**Authentication**: None required

**Response Schemas**:

**200 OK** — Service is ready

```json
{
  "status": "ready",
  "service": "string"
}
```

**503 Service Unavailable** — Service is not ready

```json
{
  "status": "not_ready",
  "service": "string"
}
```

**Field Descriptions**:
- `status` (string): Service readiness status. One of `"ready"` or `"not_ready"`.
- `service` (string): The name of the service (from the `app_name` configuration setting).

**Example Request**:
```bash
curl -X GET http://localhost:8000/ready
```

**Example Response (200 OK)**:
```json
{
  "status": "ready",
  "service": "api"
}
```

**Example Response (503 Service Unavailable)**:
```json
{
  "status": "not_ready",
  "service": "api"
}
```

**Status Codes**:
- `200 OK`: Service is ready to accept requests
- `503 Service Unavailable`: Service is not ready (e.g., during startup or maintenance)
- `405 Method Not Allowed`: HTTP method not allowed (only GET is supported)

**Use Cases**:
- Kubernetes readiness probes to determine when a pod can receive traffic
- Load balancer health checks to exclude unhealthy instances from rotation
- Orchestrator startup detection to ensure the service is fully initialized
- Monitoring systems to track service availability over time

**Implementation Notes**:
- The readiness state is managed by a module-level flag in `src/health/readiness.py`
- By default, the service starts in the ready state (`_ready = True`)
- Use `set_not_ready()` and `set_ready()` to change the state programmatically
- This is a lightweight, synchronous check suitable for frequent probe intervals
- This endpoint does not require authentication and is publicly accessible
- Only the GET HTTP method is supported; other methods return 405

---

### Health Check

#### GET /health

Returns the current health status of the API service, including the service version,
logging configuration, and database connectivity status. This endpoint is designed
for Kubernetes liveness probes and general health monitoring.

**Tags**: `health`

**Authentication**: None required

**Response**: `200 OK`

**Response Schema**:

```json
{
  "status": "string",
  "version": "string",
  "log_level": "string",
  "log_format": "string",
  "database": "string"
}
```

**Field Descriptions**:
- `status` (string): Overall service health status. One of `"ok"` (healthy) or `"degraded"` (database unavailable).
- `version` (string): Application version string (e.g., "0.1.0").
- `log_level` (string): Current configured log level (e.g., "INFO", "DEBUG").
- `log_format` (string): Current configured log format (e.g., "json", "console").
- `database` (string): Database connection status. One of `"connected"` or `"unavailable"`.

**Example Request**:
```bash
curl -X GET http://localhost:8000/health
```

**Example Response (200 OK — Healthy)**:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "log_level": "INFO",
  "log_format": "json",
  "database": "connected"
}
```

**Example Response (200 OK — Degraded)**:
```json
{
  "status": "degraded",
  "version": "0.1.0",
  "log_level": "INFO",
  "log_format": "json",
  "database": "unavailable"
}
```

**Status Codes**:
- `200 OK`: Health check completed. The response body indicates whether the service is healthy (`status: "ok"`) or degraded (`status: "degraded"`).
- `405 Method Not Allowed`: HTTP method not allowed (only GET is supported).

**Use Cases**:
- Kubernetes liveness probes to detect and restart unhealthy pods
- Monitoring dashboards to track service health over time
- Debugging and troubleshooting to identify database connectivity issues
- CI/CD pipeline validation to verify service readiness after deployment

**Implementation Notes**:
- The health check queries the database with a lightweight `SELECT 1` probe
- When the database is unreachable, the endpoint returns `status: "degraded"` with `database: "unavailable"` rather than failing with a 500 error
- The version, log level, and log format are read from the application configuration settings
- This endpoint does not require authentication and is publicly accessible
- Only the GET HTTP method is supported; other methods return 405

---

### Whoami

#### GET /whoami

Returns the name of the API service currently running. This endpoint is useful
for identifying which service instance is responding, particularly in load-balanced
or multi-region deployments.

**Tags**: `whoami`

**Authentication**: None required

**Response**: `200 OK`

**Response Schema**:

```json
{
  "service": "string"
}
```

**Field Descriptions**:
- `service` (string): The name of the API service (from the `app_name` configuration setting).

**Example Request**:
```bash
curl -X GET http://localhost:8000/whoami
```

**Example Response**:
```json
{
  "service": "api"
}
```

**Status Codes**:
- `200 OK`: Service identification returned successfully
- `405 Method Not Allowed`: HTTP method not allowed (only GET is supported)

**Use Cases**:
- Verifying which service instance responds in a distributed system
- Debugging routing issues in load-balanced deployments
- Service discovery in microservice architectures

**Implementation Notes**:
- The service name is read from the `app_name` configuration setting
- This endpoint does not require authentication and is publicly accessible
- Only the GET HTTP method is supported; other methods return 405

---

### Uptime

#### GET /uptime

Returns the service name, start time, and current uptime in seconds. This endpoint
provides information about how long the service has been running since its last
restart or deployment.

**Tags**: `uptime`

**Authentication**: None required

**Response**: `200 OK`

**Response Schema**:

```json
{
  "service": "string",
  "started_at": "string",
  "uptime_seconds": 0.0
}
```

**Field Descriptions**:
- `service` (string): The name of the service (from the `app_name` configuration setting).
- `started_at` (string): ISO-8601 timestamp when the service started (with UTC offset, e.g., "2024-01-01T00:00:00+00:00").
- `uptime_seconds` (float): Seconds elapsed since the service started, computed from the monotonic clock to ensure it never goes backwards.

**Example Request**:
```bash
curl -X GET http://localhost:8000/uptime
```

**Example Response**:
```json
{
  "service": "api",
  "started_at": "2024-01-01T00:00:00+00:00",
  "uptime_seconds": 3600.5
}
```

**Status Codes**:
- `200 OK`: Uptime information returned successfully
- `405 Method Not Allowed`: HTTP method not allowed (only GET is supported)

**Use Cases**:
- Verifying that the service was recently restarted after a deployment
- Detecting unexpectedly long uptimes that may indicate a missed restart
- Capacity planning and reliability tracking

**Implementation Notes**:
- The startup time is captured as a module-level variable when the router is first imported
- Uptime is computed using `time.monotonic()` to ensure it never goes backwards
- The timestamp is recorded using `datetime.now(UTC)` for human-readable start time
- This endpoint does not require authentication and is publicly accessible

---

### Request Statistics

#### GET /stats

Returns service request statistics including the service name, total number of
requests served, and the timestamp of the first recorded request.

**Tags**: `stats`

**Authentication**: None required

**Response**: `200 OK`

**Response Schema**:

```json
{
  "service": "string",
  "requests_served": 0,
  "first_request_at": "string"
}
```

**Field Descriptions**:
- `service` (string): The name of the service (from the `app_name` configuration setting).
- `requests_served` (integer): Total number of requests served since the service started.
- `first_request_at` (string or null): ISO-8601 timestamp of the first recorded request, or null if no requests have been served yet.

**Example Request**:
```bash
curl -X GET http://localhost:8000/stats
```

**Example Response**:
```json
{
  "service": "api",
  "requests_served": 42,
  "first_request_at": "2024-01-01T00:00:01+00:00"
}
```

**Status Codes**:
- `200 OK`: Statistics returned successfully
- `405 Method Not Allowed`: HTTP method not allowed (only GET is supported)

**Use Cases**:
- Monitoring request volume over time
- Debugging request routing issues
- Performance baseline measurement

**Implementation Notes**:
- The request counter is maintained by the `StatsCounterMiddleware` which runs on every request
- The counter is thread-safe using a threading.Lock
- This endpoint does not require authentication and is publicly accessible

---

### Server Time

#### GET /time

Returns the current UTC time in ISO-8601 format with second precision and the
service name. The time is computed at request time, never cached or module-level.

**Tags**: `time`

**Authentication**: None required

**Response**: `200 OK`

**Response Schema**:

```json
{
  "time": "string",
  "service": "string"
}
```

**Field Descriptions**:
- `time` (string): Current UTC time in ISO-8601 format with second precision and trailing Z (e.g., "2026-07-31T12:34:56Z").
- `service` (string): Service name (e.g., "api_test").

**Example Request**:
```bash
curl -X GET http://localhost:8000/time
```

**Example Response**:
```json
{
  "time": "2026-07-31T12:34:56Z",
  "service": "api_test"
}
```

**Status Codes**:
- `200 OK`: Current time retrieved successfully
- `405 Method Not Allowed`: HTTP method not allowed (only GET is supported)

**Use Cases**:
- Clock synchronization verification
- Debugging time-related issues in distributed systems
- Validating server time accuracy against NTP sources

**Implementation Notes**:
- The time is computed at request time using `datetime.now(timezone.utc)`
- Microseconds are truncated for second precision
- The timezone offset is rendered as "Z" instead of "+00:00"
- This endpoint does not require authentication and is publicly accessible

---

### Search

#### GET /search

Searches for content matching the provided query name. Returns a list of matching
results and the total count. Uses case-insensitive substring matching on user full
names.

**Tags**: `search`

**Authentication**: None required

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | The search query string. Case-insensitive substring matching on user full names. |

**Response**: `200 OK`

**Response Schema**:

```json
{
  "query": "string",
  "results": ["string"],
  "total": 0
}
```

**Field Descriptions**:
- `query` (string): The search query string that was provided.
- `results` (array of strings): List of matching user full names. Empty array if no matches found.
- `total` (integer): Total number of results found.

**Example Request**:
```bash
curl -X GET "http://localhost:8000/search?name=john"
```

**Example Response (Happy Path — Matches Found)**:
```json
{
  "query": "john",
  "results": ["John Doe", "Johnny Smith"],
  "total": 2
}
```

**Example Response (Happy Path — No Matches)**:
```json
{
  "query": "nonexistent",
  "results": [],
  "total": 0
}
```

**Example Response (Error — Missing Parameter)**:
```json
{
  "detail": "The 'name' query parameter is required"
}
```

**Status Codes**:
- `200 OK`: Search completed successfully. The response body contains the query, results list, and total count.
- `400 Bad Request`: The `name` query parameter is missing.
- `405 Method Not Allowed`: HTTP method not allowed (only GET is supported).

**Use Cases**:
- Finding users by partial name match
- Building search autocomplete features
- Filtering user lists by name substring

**Implementation Notes**:
- Uses case-insensitive substring matching on user full names
- Empty or whitespace-only queries return all users
- The search queries the database using SQLAlchemy
- This endpoint does not require authentication and is publicly accessible

---

### Domain Count

#### GET /users/count-by-domain

Returns a list of email domains and their user counts, ordered by count in
descending order. This endpoint provides a summary of the email domain distribution
among registered users.

**Tags**: `users`

**Authentication**: None required

**Response**: `200 OK`

**Response Schema**:

```json
[
  {
    "domain": "string",
    "count": 0
  }
]
```

**Field Descriptions**:
- `domain` (string): The email domain (e.g., "example.com").
- `count` (integer): The number of users registered with this domain.

**Example Request**:
```bash
curl -X GET http://localhost:8000/users/count-by-domain
```

**Example Response (Happy Path — Multiple Domains)**:
```json
[
  {
    "domain": "example.com",
    "count": 5
  },
  {
    "domain": "test.org",
    "count": 3
  },
  {
    "domain": "example.com",
    "count": 1
  }
]
```

**Example Response (Happy Path — Empty User Set)**:
```json
[]
```

**Status Codes**:
- `200 OK`: Domain counts returned successfully. The response body is a JSON array of domain/count objects.
- `405 Method Not Allowed`: HTTP method not allowed (only GET is supported).
- `503 Service Unavailable`: Database error when querying user data.

**Use Cases**:
- Analyzing email domain distribution across users
- Identifying dominant email providers
- Monitoring domain diversity in user base

**Implementation Notes**:
- The endpoint queries the database for all users and extracts email domains
- Malformed emails (without @) are filtered out
- Results are ordered by count in descending order
- The domain extraction uses case-insensitive normalization
- This endpoint does not require authentication and is publicly accessible

---

## Common Response Formats

### Success Response
All successful responses return appropriate HTTP status codes (200, 201, etc.) with a JSON body containing the requested data.

### Error Response
Error responses follow a consistent format:
```json
{
  "detail": "Error message description"
}
```

## ETag Support

The API supports HTTP ETags (Entity Tags) for conditional requests, enabling efficient
caching and reducing bandwidth usage. ETags are implemented via ASGI middleware that
automatically attaches `ETag` headers to all JSON responses and validates
`If-None-Match` headers on GET requests.

### ETag Header

All successful GET responses include an `ETag` response header containing a strong
validator string wrapped in double quotes, as defined by [RFC 9110](https://datatracker.ietf.org/doc/html/rfc9110#section-8.8.3).

**Response Header**:

| Header | Type | Description |
|--------|------|-------------|
| `ETag` | string | A strong ETag validator, e.g. `"a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"` |

**Example Response Headers**:

```
HTTP/1.1 200 OK
Content-Type: application/json
ETag: "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
```

### ETag Generation Algorithm

ETags are generated using the following deterministic algorithm:

1. **Canonical JSON Serialization**: The response body (a dict or JSON-serializable object)
   is serialized to a compact JSON string with sorted keys and minimal whitespace.
   - Keys are sorted alphabetically (`sort_keys=True`)
   - Separators are `(",", ":")` (no spaces)
   - Example: `{"b": 2, "a": 1}` becomes `{"a":1,"b":2}`

2. **SHA-256 Hashing**: The canonical JSON string is encoded as UTF-8 and hashed
   using SHA-256, producing a 256-bit (32-byte) digest.

3. **Hex Encoding**: The binary digest is converted to a 64-character lowercase
   hexadecimal string.

4. **Quoting**: The hex digest is wrapped in double quotes to produce the final
   strong ETag per RFC 9110.

**Formula**:

```
ETag = '"' + SHA-256(canonical_json(response_body)).hexdigest() + '"'
```

**Properties**:

- **Deterministic**: Identical resource state always produces the same ETag.
- **Order-independent**: Dict key ordering does not affect the ETag (keys are sorted).
- **Strong validator**: The ETag uses double quotes, indicating a strong validator
  (byte-for-byte equality).
- **64-character body**: The hex digest portion is always exactly 64 characters.

**Example**:

```python
import hashlib
import json

data = {"id": "1", "email": "test@example.com"}
canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
# Result: '{"email":"test@example.com","id":"1"}'
digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
# Result: 'a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e'
etag = f'"{digest}"'
# Result: '"a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"'
```

### Conditional Requests (If-None-Match)

Clients can use the `If-None-Match` request header to perform conditional GET
requests. When the server's current ETag matches the value(s) in `If-None-Match`,
the server responds with **304 Not Modified** and an empty body, indicating the
client's cached copy is still valid.

**Request Header**:

| Header | Type | Description |
|--------|------|-------------|
| `If-None-Match` | string | One or more ETags to match, or `*` to match any current representation |

**Header Formats**:

- Single ETag: `"a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"`
- Multiple ETags: `"etag1", "etag2", "etag3"`
- Wildcard: `*` (matches any current representation)

**Response Behavior**:

| Condition | Status Code | Response Body | ETag Header |
|-----------|-------------|---------------|-------------|
| `If-None-Match` matches current ETag | `304 Not Modified` | Empty | Current ETag |
| `If-None-Match` does not match | `200 OK` (or original status) | Full response | Current ETag |
| No `If-None-Match` header | `200 OK` (or original status) | Full response | Current ETag |
| Malformed `If-None-Match` | `200 OK` (or original status) | Full response | Current ETag |

### If-None-Match Usage Examples

**Example 1: Basic conditional GET**

```bash
# Step 1: Initial request to get the ETag
curl -v http://localhost:8000/health

# Response includes:
# ETag: "d41d8cd98f00b204e9800998ecf8427e"

# Step 2: Use the ETag in a subsequent conditional request
curl -v -H 'If-None-Match: "d41d8cd98f00b204e9800998ecf8427e"' \
  http://localhost:8000/health

# Response: 304 Not Modified (body is empty, no data transferred)
```

**Example 2: Multiple ETags**

```bash
# Client caches multiple versions and sends all known ETags
curl -v -H 'If-None-Match: "etag-old", "etag-current", "etag-future"' \
  http://localhost:8000/health

# If any of the ETags match, the server returns 304 Not Modified
```

**Example 3: Wildcard matching**

```bash
# Request 304 if the resource has changed (any version)
curl -v -H 'If-None-Match: *' \
  http://localhost:8000/health

# If the resource exists, server returns 304 Not Modified
# This is useful for DELETE operations or cache invalidation checks
```

**Example 4: Python requests library**

```python
import requests

# Step 1: Get the initial ETag
response = requests.get("http://localhost:8000/health")
etag = response.headers.get("ETag")
print(f"ETag: {etag}")  # "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"

# Step 2: Conditional GET on subsequent requests
if etag:
    response = requests.get(
        "http://localhost:8000/health",
        headers={"If-None-Match": etag}
    )
    if response.status_code == 304:
        print("Cache is still valid, using local copy")
    else:
        print("Resource changed, updating cache")
        etag = response.headers.get("ETag")
```

**Example 5: JavaScript / Fetch API**

```javascript
// Step 1: Fetch with ETag storage
let cachedETag = localStorage.getItem('health_etag');

async function fetchWithCache() {
    const headers = {};
    if (cachedETag) {
        headers['If-None-Match'] = cachedETag;
    }

    const response = await fetch('/health', { headers });

    if (response.status === 304) {
        // Cache is still valid
        console.log('Using cached data');
    } else {
        // Update cache
        const data = await response.json();
        cachedETag = response.headers.get('ETag');
        localStorage.setItem('health_etag', cachedETag);
        console.log('Cache updated:', data);
    }
}
```

### Middleware Configuration

The ETag middleware is registered globally in the application and applies to all
GET requests. It operates as follows:

1. **Intercepts** GET requests with an `If-None-Match` header
2. **Captures** the response body from the downstream application
3. **Generates** the current ETag from the response body
4. **Compares** the generated ETag against the client's `If-None-Match` value
5. **Returns** either a 304 Not Modified (match) or the full response with ETag (no match)

The middleware handles malformed `If-None-Match` headers gracefully by returning
the full resource without triggering a 304 response.

## Rate Limiting

Currently, no rate limiting is enforced. This may be added in future versions.

## Versioning

The API version is included in the response headers as `X-API-Version` and in the `/version` endpoint response.

## Support

For API support, please contact support@example.com or visit https://example.com/support.
