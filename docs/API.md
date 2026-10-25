# API reference

Base path: `/api/` (via the Next.js server in the browser, or directly on Django at `:8000`). A trailing slash is optional. All bodies are JSON. Timestamps are ISO 8601 with a time zone offset.

## Error format

Every error response has the same shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Please correct the highlighted fields.",
    "fields": {
      "phone": "Enter a valid 10-digit Indian mobile number, e.g. +91 98765 43210.",
      "email": "Enter a valid email address, e.g. name@example.com."
    }
  }
}
```

| Status | `code` examples | When |
|---|---|---|
| 400 | `validation_error` | Invalid input (`fields` gives per-field messages) |
| 404 | `not_found` | Unknown candidate, message, batch or template |
| 409 | `retry_not_allowed`, `cancel_not_allowed`, `duplicate_candidate`, `request_id_conflict` | Action not allowed in the current state (message says why) |
| 429 | `throttled` | Too many write requests |
| 500 | `server_error` | Unexpected error (details are logged, never returned) |

## Candidates

### `GET /candidates`

| Query param | Example | Meaning |
|---|---|---|
| `search` | `kumar`, `98765 43210`, `A1B2C3` | Name, email or ID (case-insensitive); mobile digits (3+ digits, spacing ignored) |
| `status` | `failed,none` | Latest message status; `none` = never messaged |
| `ordering` | `-last_message_at`, `full_name`, `candidate_code`, `phone` | Prefix `-` for descending; candidates never messaged go last |
| `page`, `page_size` | `2`, `25` | Pagination (max 100) |

```json
{
  "count": 21,
  "next": "http://…/api/candidates?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "candidate_code": "A1B2C3",
      "full_name": "Krishna Khandelwal",
      "phone": "+919876543210",
      "phone_display": "+91 9876543210",
      "email": "krishna.khandelwal@example.com",
      "created_at": "2026-08-27T02:20:02+05:30",
      "last_message": { "id": "41d8…", "status": "read", "status_label": "Read", "created_at": "2026-10-23T10:47:00+05:30" }
    }
  ]
}
```

### `POST /candidates`

```json
{ "full_name": "Priya Shah", "phone": "098765 43210", "email": "Priya.Shah@Example.com" }
```

→ `201` with the candidate. The name is trimmed, the phone becomes `+919876543210` and the email is lower-cased. A duplicate phone or email returns `400`, naming the existing candidate.

### `GET /candidates/{id}` · `DELETE /candidates/{id}` (`204`, also deletes their history)

### `POST /candidates/bulk-delete`

```json
{ "ids": [3, 7, 9] }
```

→ `{"deleted": 2, "not_found": [9]}`

## Sending

Sending is asynchronous. The API saves the messages and returns `202 Accepted`; the worker delivers them. Replaying a request with the same `client_request_id` returns the original result with `200` and creates nothing new.

### `POST /candidates/{id}/messages` (one candidate)

```json
{
  "body": "Hi {{first_name}}, your interview is tomorrow at 11:00 AM.",
  "client_request_id": "c3f1a2b4-…",
  "provider": "simulator_email",
  "template_id": 1,
  "scheduled_at": "2026-10-27T09:30:00+05:30"
}
```

Only `body` is required. `provider` defaults to the first configured provider (`simulator` = SMS). Template variables: `{{first_name}}`, `{{full_name}}`, `{{candidate_id}}`, `{{phone}}`, `{{email}}`; unknown variables are rejected. `scheduled_at` must be between 1 minute and 30 days ahead. The response is the message (see below).

### `POST /message-batches` (many candidates)

Same body plus `"candidate_ids": [1, 2, 3]` (duplicates ignored; max 500). The response is the batch:

```json
{
  "id": "ed3d7bf1-…",
  "recipient_count": 5,
  "channel": "sms",
  "summary": { "total": 5, "processing": 0, "scheduled": 0, "submitted": 2, "delivered": 2, "read": 1,
               "failed": 3, "cancelled": 0, "retrying": 0, "complete": true },
  "messages": [ { "…message fields…": "", "candidate": { "id": 81, "full_name": "Rohit Deshmukh", "candidate_code": "N5O6P7", "phone_display": "+91 9820041000" } } ]
}
```

`submitted` counts messages the provider accepted (sent, delivered or read). `complete` becomes `true` once no recipient is queued or sending.

### `GET /message-batches/{id}`: per-recipient results (poll this)

## Messages

### `GET /messages/{id}`

```json
{
  "id": "2d592b19-…",
  "body": "Hi Rohit, your interview is scheduled for tomorrow at 11:00 AM.",
  "channel": "sms",
  "provider": "simulator",
  "provider_label": "SimuText (simulated SMS provider)",
  "status": "failed",
  "provider_message_id": null,
  "attempt_count": 1,
  "max_attempts": 5,
  "retry_scheduled": false,
  "error": {
    "category": "invalid_recipient",
    "title": "Invalid mobile number",
    "explanation": "The provider says this number can't receive messages. Check the candidate's mobile number; retrying won't help.",
    "technical_detail": "Provider responded with HTTP 422 (invalid_recipient)."
  },
  "can_retry": false,
  "retry_block_reason": "This failure is permanent, so retrying would fail again.",
  "can_cancel": false,
  "created_at": "…", "sent_at": null, "delivered_at": null, "read_at": null, "failed_at": "…",
  "events":   [ { "kind": "queued", "source": "system", "detail": "Queued for sending.", "applied": true, "occurred_at": "…" } ],
  "attempts": [ { "number": 1, "trigger": "initial", "outcome": "failed", "error_code": "invalid_recipient", "http_status": 422 } ]
}
```

### `GET /candidates/{id}/messages`: history, newest first (paginated, 50 per page)

### `POST /messages/{id}/retry`

`202` with the re-queued message, or `409 retry_not_allowed` with the reason. Possible reasons: the message isn't failed, the failure is permanent, or the retry limit has been reached.

### `POST /messages/{id}/cancel`

Scheduled messages only; otherwise `409 cancel_not_allowed`.

## Templates

| Method & path | Notes |
|---|---|
| `GET /templates` | Not paginated |
| `POST /templates` | `{"name", "body"}`; names are unique (case-insensitive); variables validated |
| `PATCH /templates/{id}` · `DELETE /templates/{id}` | |
| `GET /template-variables` | `[{"name": "first_name", "token": "{{first_name}}", "description": "…"}]` |

## Provider

### `GET /provider/health`

```json
{
  "status": "operational",
  "default_provider": "simulator",
  "providers": [
    { "name": "simulator", "display_name": "SimuText (simulated SMS provider)", "channel": "sms",
      "simulated": true, "status": "operational", "detail": "All systems operational.", "checked_at": "…" },
    { "name": "simulator_email", "display_name": "SimuMail (simulated email provider)", "channel": "email",
      "simulated": true, "status": "operational", "detail": "All systems operational.", "checked_at": "…" }
  ],
  "stats": { "total": 14, "sent": 8, "delivered": 7, "read": 6, "failed": 3, "in_progress": 0, "scheduled": 0 },
  "demo_controls_enabled": true,
  "scenarios": [ { "channel": "sms", "match": "Number ends in 000", "behaviour": "Invalid recipient (permanent failure, no retry)" } ]
}
```

### `POST /provider/simulator/outage`

`{"enabled": true}`. Only when `DEMO_CONTROLS_ENABLED=true`; otherwise `403`.

## Webhooks (provider → platform)

`POST /webhooks/provider/{simulator|simulator_email}/`, with header `X-Sim-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, "t.body")>`.

```json
{ "event_id": "evt_…", "type": "message.status", "message_id": "sim_…", "client_reference": "<our message id>",
  "status": "delivered", "occurred_at": "2026-10-26T03:50:10+00:00", "error": null }
```

Responses: `200 {"result": "applied" | "ignored" | "duplicate" | "unknown_message"}`; `401` bad or old signature; `400` malformed; `404` unknown provider.

## Health

`GET /health` → `{"status": "ok"}` (checks the database).
