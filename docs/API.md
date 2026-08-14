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
