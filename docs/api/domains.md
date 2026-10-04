# List User Domains

`GET /users/domains`

Returns a JSON array of the distinct email domains of the users in the database,
in alphabetical order. It takes no parameters and returns no counts — for the
number of users behind each domain use `GET /users/count-by-domain`.

An address with no usable domain part contributes nothing, and a database with
no users yields an empty array rather than an error.

**Tags**: `users`
**Authentication**: None required.
**Request body**: None.
**Query parameters**: None.

## Description

Every live user's address is read, the domain part is extracted with the
project's one extraction rule (`src/users/domain_extraction.py`), and the
result is deduplicated and sorted. Three consequences are worth knowing:

- **Distinct**: three users on `example.com` produce one entry, not three.
- **Case-folded**: `User@Example.COM` and `user@example.com` are the same
  domain, so they contribute one lowercase entry.
- **Alphabetical**: the array is sorted by the endpoint, never by the order the
  rows happen to come back in.

Soft-deleted users (`DELETE /users/{user_id}`) are excluded, as in every other
read in this feature.

## Parameters

None. The route accepts no path parameters, no query parameters and no body.

## Response

`200 OK` — a bare JSON array of strings. There is no wrapping object: the body
is the array itself, serialized from the `DomainListResponse` root model.

| Position | Type   | Description                                                        |
|----------|--------|--------------------------------------------------------------------|
| [n]      | string | One distinct domain, lowercase, the part after the `@` of an address |

## Examples

### 200 OK — several domains

**Request**

```bash
curl -X GET http://localhost:8000/users/domains
```

**Response**

```json
[
  "alpha.example",
  "beta.example",
  "example.com",
  "test.org"
]
```

### 200 OK — no users, or no usable addresses

An empty answer is a success, not a 404 and not a 500.

**Request**

```bash
curl -X GET http://localhost:8000/users/domains
```

**Response**

```json
[]
```

### 503 Service Unavailable — database failure

The rows could not be read. Errors use the API-wide error shape.

**Request**

```bash
curl -X GET http://localhost:8000/users/domains
```

**Response**

```json
{
  "detail": "Database unavailable: connection to server at 'localhost', port 5432 failed: Connection refused"
}
```

## Error Response Format

Errors answer with the single `detail` key every other endpoint in this API
uses:

```json
{
  "detail": "Error message description"
}
```

| Code | Body                                                                                     |
|------|------------------------------------------------------------------------------------------|
| 503  | `{"detail": "Database unavailable: <driver message>"}` — the read of the addresses failed. |
| 405  | `{"detail": "Method Not Allowed"}` — the router's own refusal, not this endpoint's.      |

## Status Codes

| Code | Meaning                                                                          |
|------|----------------------------------------------------------------------------------|
| 200  | The distinct domains were read. The body is the array, empty when there are none.  |
| 405  | HTTP method not allowed: this endpoint is read-only and serves `GET` only.         |
| 503  | Database unavailable while reading the user addresses.                             |

## Implementation Notes

- The route lives in `src/users/router.py` (`get_user_domains`) and reads
  through `crud.get_distinct_domains` in `src/users/crud.py`.
- The addresses come back to Python rather than being deduplicated in SQL,
  because case-folding and the "no usable domain" rule are what define a domain
  here, and neither is a `DISTINCT` over the column.
- The read is `select(User.email).where(User.deleted_at.is_(None))`, so
  soft-deleted users are out of the list.
- A `SQLAlchemyError` is translated at the route into `503` with the detail
  `Database unavailable: <error>`; the failure is logged, not leaked as a
  traceback.
- The route is registered ahead of `GET /users/{user_id}` on purpose. FastAPI
  answers the first route that matches, so a literal path declared after the
  ID route would be swallowed and refused as a malformed UUID.
- The route is registered with the rest of the users router in `src/main.py`
  and appears in the interactive docs at `/docs`.

## Related Endpoints

- `GET /users/count-by-domain` — the same domains with a user count each,
  ordered by count descending, with an optional `min_count` filter.
- `GET /users` — the users behind the domains.
- `GET /users/count` — total users, the population this list is drawn from.
