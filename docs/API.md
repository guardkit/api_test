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

## Rate Limiting

Currently, no rate limiting is enforced. This may be added in future versions.

## Versioning

The API version is included in the response headers as `X-API-Version` and in the `/version` endpoint response.

## Support

For API support, please contact support@example.com or visit https://example.com/support.
