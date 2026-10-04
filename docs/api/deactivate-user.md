# Deactivate User

`PATCH /users/{user_id}/deactivate`

Sets an existing, active user's `is_active` flag to `false` and returns the
updated user. The row is kept, so the account can be brought back later with
`PUT /users/{user_id}` (`{"is_active": true}`). Deactivation is not a delete:
`deleted_at` is untouched, so the user still appears in `GET /users` and moves
from `active_count` to `inactive_count` in `GET /users/active-count`.

**Tags**: `users`
**Authentication**: None required. Unlike `DELETE /users/{user_id}`, this route
checks no `X-Auth-Token` header of its own.
**Request body**: None.

## Path Parameters

| Parameter | Type   | Required | Description                     |
|-----------|--------|----------|---------------------------------|
| user_id   | string | Yes      | UUID of the user to deactivate  |

## Response

`200 OK` — the `UserPublic` object, as returned by every other user endpoint.

| Field       | Type           | Description                                        |
|-------------|----------------|----------------------------------------------------|
| id          | string (UUID)  | Identifier of the user                             |
| email       | string         | Email address of the user                          |
| domain      | string \| null | Domain part of the email address                   |
| name        | string \| null | Display name, derived from `full_name`             |
| full_name   | string \| null | Full name as stored                                |
| is_active   | boolean        | `false` after a successful deactivation            |
| created_at  | string         | Creation timestamp, ISO 8601                       |
| updated_at  | string         | Timestamp of the last write, ISO 8601              |
| deleted_at  | string \| null | Soft-delete timestamp; `null` for a live user      |

## Examples

### 200 OK — active user deactivated

**Request**

```bash
curl -X PATCH http://localhost:8000/users/550e8400-e29b-41d4-a716-446655440000/deactivate
```

**Response**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "john.doe@example.com",
  "domain": "example.com",
  "name": "John Doe",
  "full_name": "John Doe",
  "is_active": false,
  "created_at": "2026-10-04T12:00:00+00:00",
  "updated_at": "2026-10-04T12:05:00+00:00",
  "deleted_at": null
}
```

### 404 Not Found — unknown or soft-deleted id

```bash
curl -X PATCH http://localhost:8000/users/00000000-0000-4000-8000-000000000000/deactivate
```

```json
{
  "detail": "User with id '00000000-0000-4000-8000-000000000000' not found"
}
```

### 409 Conflict — already inactive

```bash
curl -X PATCH http://localhost:8000/users/550e8400-e29b-41d4-a716-446655440000/deactivate
```

```json
{
  "detail": "User with id '550e8400-e29b-41d4-a716-446655440000' is already inactive"
}
```

## Status Codes

| Code | Meaning                                                                                     |
|------|---------------------------------------------------------------------------------------------|
| 200  | The user was active and is now inactive. The body is the updated user.                      |
| 400  | Invalid user ID format. The `user_id` path parameter must be a valid UUID.                  |
| 404  | No live user with that ID — the ID is unknown, or the user was soft-deleted with `DELETE /users/{user_id}`. |
| 409  | The user is already inactive, so there is nothing to deactivate.                             |
| 503  | Database error while reading or writing the user.                                            |

## Implementation Notes

- The route lives in `src/users/router.py` (`deactivate_user`) and writes
  through `crud.deactivate_user`, which commits, so the change is visible to the
  next request.
- The check and the write are one guarded `UPDATE` whose `WHERE` clause requires
  the row to be live and active. Only one caller can claim a given user, so two
  concurrent requests cannot both report success: the loser gets 409.
- When the claim matches nothing, one read decides the answer: no live row
  answers 404, a live but inactive row answers 409.
- A soft-deleted user is never claimed, so deactivating one answers 404 rather
  than reviving it.
- Repeating the call is safe: nothing is written when the claim does not match.
- The route is registered with the rest of the users router in `src/main.py`
  and appears in the interactive docs at `/docs`.

## Related Endpoints

- `PUT /users/{user_id}` — reactivate with `{"is_active": true}`, or change
  other fields.
- `DELETE /users/{user_id}` — soft-delete instead of deactivate.
- `GET /users/{user_id}` — read the user back after deactivating.
