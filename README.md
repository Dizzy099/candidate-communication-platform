# Candidate Communication Platform

A recruiter tool for messaging candidates one at a time or in bulk, and for tracking every message from **Queued → Sent → Delivered → Read**. It handles failures honestly: it shows plain-English reasons, retries automatically when that's safe, and offers a manual **Retry** only when retrying can help.

**Live demo:** https://candidate-communication-platform.onrender.com (free tier: the first load after idling takes about a minute; demo data resets on restart)

Stack: **Next.js + React + TypeScript + Material UI** frontend, **Python + Django REST Framework** backend, a background **worker**, and a separate **provider simulator** service.

![Candidate list](docs/screenshots/01-candidates.png)

| Delivery results for a bulk send | Communication history with a failure |
|---|---|
| ![Delivery results](docs/screenshots/06-delivery-results.png) | ![History](docs/screenshots/07-history-failure.png) |

---

## Contents

1. [What it does](#1-what-it-does)
2. [Run it locally (2 commands)](#2-run-it-locally)
3. [Five-minute demo script](#3-five-minute-demo-script)
4. [Architecture](#4-architecture)
5. [Message statuses and update rules](#5-message-statuses-and-update-rules)
6. [Failures, retries and guarantees](#6-failures-retries-and-guarantees)
7. [The provider simulator](#7-the-provider-simulator)
8. [API overview](#8-api-overview)
9. [Configuration](#9-configuration)
10. [Tests](#10-tests)
11. [Deployment](#11-deployment)
12. [Security and scope decisions](#12-security-and-scope-decisions)
13. [Assumptions, limitations, known issues](#13-assumptions-limitations-known-issues)
14. [Project structure](#14-project-structure)

Further reading: [design fidelity notes](docs/DESIGN_NOTES.md) · [API reference](docs/API.md) · [manual test checklist](docs/MANUAL_TEST_CHECKLIST.md) · [implementation checklist](IMPLEMENTATION_CHECKLIST.md)

---

## 1. What it does

| Assignment requirement | How it works here |
|---|---|
| **Candidate management**: add, view all, search, view details | Paginated table (10/25/50 rows). Search covers name, mobile, email and candidate ID. Sort and status filters sit in the column headers. Adding validates Indian mobile numbers and normalises them to `+91…`. Duplicate numbers or emails are rejected with the existing candidate's name. Delete one or many after a confirmation. |
| **Send a message** to one candidate | Select a row and click **Send message**, or click a name and use **Send message** in the history panel. |
| **Bulk messaging** | Select any number of candidates (selection survives paging and search), compose once, confirm the count, send. Each recipient gets its **own message record**, tracked independently. |
| **Message status** | Scheduled · Queued · Sending · Sent · Delivered · Read · Failed · Cancelled. Delivered and Read appear **only after the provider confirms them**. |
| **External communication provider** | A separate **SimuText** simulator service. It has its own process, database and HTTP API, and returns reference IDs. |
| **Status updates** from the provider | HMAC-signed webhooks. Duplicate, out-of-order and stale events are handled safely. The browser polls every 2.5–4 s (shown in the UI; no real-time push is claimed). |
| **Failure handling** | Each failure is classified into a category with recruiter-friendly wording. No stack traces reach the browser. |
| **Communication history** | Newest first. Shows date and time, channel, status, body, failure reason, a Retry or Cancel action, and an expandable audit timeline. |
| **UX states** | Loading skeletons, empty states with the design's illustration, "no matches", request errors with **Try again**, live "Sending…" progress, and honest bulk outcomes. |

**Bonus features (all five implemented)**

| Bonus | Implementation |
|---|---|
| A. Message templates | Save the composed text as a template, reuse it, insert variables (`{{first_name}}`, `{{full_name}}`, `{{candidate_id}}`, `{{phone}}`, `{{email}}`). Variables are filled in per candidate on the server; unknown variables are rejected. |
| B. Scheduled messages | "Schedule for later" uses your local time zone and is stored in UTC. The worker sends it when due. It shows as **Scheduled** and can be **cancelled**. |
| C. Multiple providers | Choose **SMS · SimuText** or **Email · SimuMail** per message. Each has its own adapter, recipient type, webhook route and health status. |
| D. Provider health | Header indicator: status per provider, message stats, test numbers, and an optional "simulate outage" switch for demos. |
| E. Retry failed messages | Automatic bounded retries for temporary failures; manual **Retry** for eligible failures; permanent failures explain why retrying is blocked. |

---

## 2. Run it locally

**You need:** [Python 3.11+](https://www.python.org/downloads/) and [Node.js 18.18+](https://nodejs.org/) (20 or 22 LTS recommended). Open a terminal (on Windows: PowerShell) in this folder.

```bash
python scripts/setup_dev.py   # one time: installs everything, creates databases, loads demo data
python scripts/dev.py         # starts all four processes; press Ctrl+C to stop
```

Then open **http://localhost:3000**.

`setup_dev.py` creates a Python virtual environment (`.venv`) and installs the Python and npm packages. It writes `backend/.env` and `simulator/.env` with freshly generated shared secrets, creates both SQLite databases and loads fictional demo data. `dev.py` runs these together:

| Process | Address | Role |
|---|---|---|
| `web` | http://localhost:3000 | Next.js UI. Proxies `/api/*` to Django |
| `api` | http://127.0.0.1:8000 | Django REST API and webhook receiver |
| `worker` | (none) | Sends queued and scheduled messages; automatic retries |
| `simulator` | http://127.0.0.1:8001 | SimuText / SimuMail fake provider |

**Reset the demo data** at any time:

```bash
cd backend && ../.venv/Scripts/python manage.py seed_demo --reset      # Windows
cd backend && ../.venv/bin/python manage.py seed_demo --reset          # macOS / Linux
```

**Alternative: Docker (PostgreSQL)**

```bash
docker compose up --build      # then open http://localhost:3000
```

---

## 3. Five-minute demo script

1. **List and search.** Type `9876` or `kumar` in Search. Open the **Status** filter in the column header and choose *Failed*.
2. **Add a candidate.** Click **Add candidate**, enter a short mobile number, see the inline error, fix it, save. A success toast appears and the new candidate is at the top.
3. **Bulk send with mixed outcomes.** Select *Rohit Deshmukh* (invalid number), *Neha Joshi* (one temporary error), *Pooja Iyer* (needs a manual retry), *Deepa Kumar* (delivery fails the first time) and *Sneha Kulkarni* (normal). Click **Send message**, pick the *Interview reminder* template, then **Send to 5 candidates** and confirm.
4. **Watch the toast.** It counts progress live ("Sending to 5 candidates… 3 of 5 processed · 1 retrying after a temporary error"), then reports the honest outcome: **"Message sent to 2 of 5 candidates. 3 failed."**
5. **View details.** Each recipient shows its own status and reason. Rohit's failure is permanent, so there's no Retry button. Click **Retry 2 failed**, or Retry on Pooja, and watch it move to Sent → Delivered → Read.
6. **History.** Click *Deepa Kumar*. The failure explains itself; open **Details** for the provider reference, attempts and the full audit trail.
7. **Provider outage.** Click the green **Simulated providers** pill and switch on *Simulate provider outage*. The pill turns red. Send a message: history shows **Retrying · Messaging service unavailable**, and the platform waits as long as the provider asks (`Retry-After: 10`). Switch the outage off within about 20 s and the automatic retry succeeds. Leave it on and the message becomes **Failed** with a **Retry** button.
8. **Email + schedule.** Send to one candidate via **Email · SimuMail** with *Schedule for later*. The message shows **Scheduled** in history and can be cancelled.

---

## 4. Architecture

```mermaid
flowchart LR
  B["Browser<br/>Next.js + MUI"] -- "/api/* (same origin)" --> N["Next.js server<br/>proxy"]
  N --> A["Django REST API"]
  A -- "short transactions" --> DB[("PostgreSQL / SQLite")]
  W["Worker<br/>run_worker"] -- "claim due messages" --> DB
  W -- "POST /v1/messages<br/>Bearer key + Idempotency-Key" --> S["SimuText / SimuMail<br/>simulator service"]
  S --- SDB[("Simulator DB")]
  S -- "signed webhooks<br/>X-Sim-Signature" --> A
```

| Decision | Why |
|---|---|
| **API never calls the provider.** It writes `queued` messages in one short transaction and returns `202 Accepted` | A slow provider can't hold a database transaction or an HTTP request open. One recipient's failure can't block another. Large batches are written in a single bulk insert. |
| **Database-backed worker** (`manage.py run_worker`) instead of Celery + Redis | Same reliability properties for this scale (exclusive claiming, leases, backoff, scheduling) with zero extra infrastructure. The trade-off is documented in §13. |
| **Exclusive claiming with a conditional UPDATE** | `UPDATE … SET status='sending' WHERE id=? AND status IN ('queued','scheduled')`. Exactly one worker wins, on SQLite and PostgreSQL alike. |
| **Leases** on claimed messages | If a worker dies mid-send, the message is re-queued after 60 s with the *same* idempotency key. |
| **Provider abstraction** (`messaging/providers/`) | Business logic depends only on the `CommunicationProvider` interface (`send`, `health`, `parse_webhook`). Adding Twilio or WhatsApp means adding one adapter class. |
| **The simulator is a separate service** | Mirrors a real integration: authenticated HTTP out, signed webhooks in, its own state, its own failures. |
| **Polling, not push** | Status updates reach the backend by webhook; the browser polls (4 s list, 2.5 s history, 1 s while a bulk send is in progress). Polling pauses in background tabs. The UI says it refreshes rather than claiming real time. |
| **Next.js proxies `/api/*`** | One public origin, no CORS in normal use, and the API and simulator can stay private in deployment. |

---

## 5. Message statuses and update rules

| Status | Meaning | Set by |
|---|---|---|
| `scheduled` | Waiting for its scheduled time | API |
| `queued` | Saved, waiting for the worker (also while waiting to auto-retry; the UI shows **Retrying**) | API / worker |
| `sending` | Claimed by the worker; provider call in progress | Worker |
| `sent` | **Accepted by the provider** (not yet confirmed delivered) | Worker, from the provider's response |
| `delivered` | Provider confirmed delivery | Webhook only |
| `read` | Provider confirmed it was read | Webhook only |
| `failed` | Could not be sent or delivered; `error_category` says why | Worker or webhook |
| `cancelled` | A scheduled message cancelled before sending | API |

**Webhook rules** (`messaging/services/status_updates.py`, all covered by tests):

1. **Duplicates.** An event ID that has already been stored is acknowledged (`200`) and ignored. A unique constraint on `(provider, provider_event_id)` makes this race-safe.
2. **Forward only.** `sent → delivered → read`. A late or repeated lower status is recorded in the audit trail as *ignored* and never regresses the message. For example, `read` arriving before `delivered` leaves the message as Read.
3. **No failure after success.** A `failed` report for an already delivered message is ignored.
4. **Superseded sends.** After a manual retry of a delivery failure, events for the old provider message can't touch the new attempt.
5. **Provider truth wins.** If our request timed out but the provider actually accepted and delivered the message, the delivery is applied and the pending retry is cancelled.
6. **Unknown messages** (for example, the candidate was deleted) are recorded and acknowledged, so the provider doesn't retry forever.
7. **Authenticity.** HMAC-SHA256 over `timestamp.body`, compared in constant time; requests older than 5 minutes are rejected (replay protection).

---

## 6. Failures, retries and guarantees

| Failure category | Example cause | Automatic retry | Manual Retry | Recruiter sees |
|---|---|---|---|---|
| `invalid_recipient` | Provider says the number or address can't receive messages (422) | No | **No** (permanent) | "Invalid mobile number" / "Invalid email address" |
| `content_rejected` | Message too long or blocked (400) | No | No | "Message rejected" |
| `rate_limited` | 429 + `Retry-After` | Yes, after `Retry-After` | Yes | "Sending too fast" |
| `provider_error` | 5xx from provider | Yes, exponential backoff | Yes | "Temporary provider error" |
| `provider_unavailable` | Timeout, connection refused, 503 outage | Yes, exponential backoff | Yes | "Messaging service unavailable" |
| `delivery_failed` | Accepted, later reported undeliverable | No | Yes (new provider send) | "Not delivered" |
| `configuration` | 401/403: bad credentials | No | Yes, once an admin fixes it | "Messaging not configured" |
| `unknown` | Anything unclassified | No | Yes | "Unexpected provider response" |

* **Bounded automatic retries.** Up to 3 attempts in total, with backoff of 2 s then 4 s (capped at 60 s; all configurable). After that the message is **Failed** and, if eligible, manually retryable.
* **Retry limit.** 5 attempts in total per message, automatic plus manual. The UI explains when the limit is reached.
* **History is preserved.** Every attempt is a `MessageAttempt` row and every step is a `MessageEvent`. A retry never creates a second message record.
* **Idempotency, honestly stated.** Every submission carries an `Idempotency-Key`. Retries of the same submission reuse it, so a provider that honours idempotency keys (SimuText does) will not send twice even after a timeout. Double-clicks and repeated form submits are de-duplicated with a per-compose `client_request_id`. The system gives **at-least-once submission with provider-side de-duplication**. It does **not** claim exactly-once delivery: that depends on the provider.

---

## 7. The provider simulator

`simulator/` is a separate small Django service with its own SQLite database. It exposes a provider-style API:

| Endpoint | Purpose |
|---|---|
| `POST /v1/messages` | Submit (Bearer API key + `Idempotency-Key`). Returns `{id, status: "sent"}` |
| `GET /v1/messages/<id>` | Current status |
| `GET /v1/health` | `operational` or `outage` |
| `POST /v1/simulator/outage` | Demo control to start or stop an outage |

A background dispatcher delivers status events to the platform's webhook. It delivers at least once, retries with backoff, and gives up after 8 attempts. Default timing: delivered after 3 s, read after 8 s. There is a token-bucket rate limit (20/s, burst 40).

**Deterministic scenarios.** There is no randomness, so the demo behaves the same way every time.

| SMS number ends in | Behaviour |
|---|---|
| `000` | Invalid recipient (422) every time |
| `111` | Temporary error (500) on the first attempt, then sent by automatic retry |
| `222` | Rate limited (429, `Retry-After: 3`) once, then sent |
| `333` | First message to the number: sent, then **delivery fails**; later messages deliver |
| `444` | Delivered, never read |
| `555` | `read` arrives *before* `delivered`, and every event is sent **twice** |
| `666` | Fails the 3 automatic attempts; the **manual retry succeeds** |
| `777` | Always fails temporarily (demonstrates the retry limit) |
| anything else | sent → delivered → read |

| Email address contains | Behaviour |
|---|---|
| `bounce` | Mailbox doesn't exist (permanent) |
| `deferred` | First email fails delivery; retry succeeds |

The seeded demo data includes one candidate per scenario (see `backend/messaging/management/commands/seed_demo.py`). The UI shows the same table under **Simulated providers → Test numbers**.

> **Nothing is really sent.** SimuText and SimuMail are simulations and are labelled as such everywhere in the UI. A real provider (for example Twilio or the WhatsApp Cloud API) would be a new class implementing `CommunicationProvider`; no business logic changes.

---

## 8. API overview

All endpoints are under `/api/`; a trailing slash is optional. Errors always look like `{"error": {"code", "message", "fields"?}}`. Full reference: [docs/API.md](docs/API.md).

| Method & path | Purpose |
|---|---|
| `GET /candidates?search=&status=&ordering=&page=&page_size=` | List and search, with each candidate's latest message status (single query, no N+1) |
| `POST /candidates` | Add a candidate (validated, normalised, duplicates rejected) |
| `GET / DELETE /candidates/{id}` | View or delete (cascades history) |
| `POST /candidates/bulk-delete` | Delete many |
| `GET /candidates/{id}/messages` | Communication history, newest first, with attempts and events |
| `POST /candidates/{id}/messages` | Message one candidate → `202` |
| `POST /message-batches` | Bulk send → `202` with per-recipient messages |
| `GET /message-batches/{id}` | Per-recipient results and summary |
| `GET /messages/{id}` · `POST /messages/{id}/retry` · `POST /messages/{id}/cancel` | Detail, manual retry, cancel a scheduled message |
| `GET/POST/PATCH/DELETE /templates` · `GET /template-variables` | Templates |
| `GET /provider/health` · `POST /provider/simulator/outage` | Provider health and stats; demo outage switch |
| `POST /webhooks/provider/{name}/` | Provider status webhooks (HMAC-verified) |

---

## 9. Configuration

Each service reads its own `.env` file (`backend/.env`, `simulator/.env`). `setup_dev.py` generates them from the `.env.example` files, which contain **placeholders only**.

| Variable (backend) | Default | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | `false` | Development mode. Production refuses to start without a secret key |
| `DJANGO_SECRET_KEY` | (required unless debug) | Django signing key |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hostnames the API answers |
| `DATABASE_URL` | SQLite file | e.g. `postgres://user:pass@host:5432/db` |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Only needed if the browser calls the API directly |
| `PROVIDER_BACKENDS` | `simulator,simulator_email` | Enabled providers; the first is the default |
| `PROVIDER_BASE_URL` | `http://127.0.0.1:8001` | Simulator address |
| `PROVIDER_API_KEY` / `PROVIDER_WEBHOOK_SECRET` | (none) | Must match `SIM_API_KEY` / `SIM_WEBHOOK_SECRET` |
| `PUBLIC_WEBHOOK_BASE_URL` | `http://127.0.0.1:8000` | Where the provider sends webhooks |
| `DEMO_CONTROLS_ENABLED` | `false` | Shows the "simulate outage" switch |
| `MESSAGE_MAX_ATTEMPTS` / `MESSAGE_AUTO_ATTEMPTS` | `5` / `3` | Retry limits |
| `RETRY_BACKOFF_BASE_SECONDS` / `RETRY_BACKOFF_MAX_SECONDS` | `2` / `60` | Backoff |
| `API_WRITE_THROTTLE_RATE` | `120/min` | Per-client limit on write requests |

| Variable (simulator) | Default | Purpose |
|---|---|---|
| `SIM_API_KEY`, `SIM_WEBHOOK_SECRET` | (none) | Shared with the backend |
| `SIM_DELIVERY_DELAY_SECONDS`, `SIM_READ_DELAY_SECONDS` | `3`, `8` | Status timing |
| `SIM_RATE_LIMIT_PER_SECOND`, `SIM_RATE_LIMIT_BURST` | `20`, `40` | Throttling |

Frontend: `API_ORIGIN` (default `http://127.0.0.1:8000`) is where Next.js proxies `/api/*`. It is read at build time.

---

## 10. Tests

| Suite | Command | Result (latest run) |
|---|---|---|
| Backend (Django) | `cd backend && ../.venv/Scripts/python manage.py test` | **85 passed** (SQLite; also passed on PostgreSQL 16 in Docker) |
| Simulator | `cd simulator && ../.venv/Scripts/python manage.py test` | **18 passed** |
| Frontend unit (Vitest) | `cd frontend && npm test` | **17 passed** |
| Type check / lint | `npm run typecheck` · `npm run lint` | clean |
| Production build | `npm run build` | succeeds |
| End-to-end (Playwright, real browser + full stack) | start the stack, then `cd frontend && npx playwright test` | **7 passed**: on the dev stack, Docker Compose with PostgreSQL, the single-container image and the live Render site |

(On macOS/Linux use `../.venv/bin/python`. For the first Playwright run, install the browser with `npx playwright install chromium`.)

What's covered: validation and normalisation, duplicates, search, filters, ordering, N+1 guard, single and bulk sends, mixed outcomes, independent recipients, classification of every error type, backoff and `Retry-After`, auto-retry limits, manual retry eligibility and recording, idempotent double submits, lease recovery, scheduling and cancelling, every webhook rule (duplicate, out-of-order, stale, superseded, unknown, timeout-then-delivered), signature verification, multiple providers, simulator scenarios and its dispatcher, plus browser journeys for add, search, delete, single send with live status updates, bulk with retries, and email.

---

## 11. Deployment

**Single container (recommended for a free demo).** `deploy/Dockerfile` runs Next.js, the API, the worker and the simulator in one container. Only Next.js is public; Django and the simulator listen on `127.0.0.1` inside the container. Secrets are generated at boot if they aren't provided. SQLite lives in `/data`.

```bash
docker build -f deploy/Dockerfile -t ccp-demo .
docker run -p 3000:3000 ccp-demo        # open http://localhost:3000
```

**Render (free).** Push this repository to GitHub, then in Render choose **New → Blueprint** and select the repo. `render.yaml` creates one free Docker web service with generated secrets. Free instances sleep when idle (the first request takes about a minute) and the file system is reset on restart, so the demo data starts fresh each time. That's intended for a demo.

**Production-style.** `docker compose up --build` runs PostgreSQL, the API (gunicorn), the worker, the simulator and the web app as separate containers. For a real deployment, replace the simulator with a real provider adapter, set real secrets, and put the API behind authentication (§12).

---

## 12. Security and scope decisions

| Topic | Decision |
|---|---|
| **Authentication** | **Not implemented.** The assignment and design have no login, and this is a single shared recruiter workspace. A public demo is protected by fictional data, write throttling, input limits and resettable data. Production would add Django auth (or SSO) with per-recruiter permissions. |
| Secrets | Environment variables only; `.env` files are git-ignored; `.env.example` holds placeholders. |
| Webhooks | HMAC-SHA256 signatures, a 5-minute replay window, constant-time comparison, a 64 KB body limit. |
| Errors | One consistent JSON error format; unexpected exceptions are logged server-side and returned as a generic 500 (tested). |
| Logging | Log lines reference opaque IDs; candidate contact details and message bodies are not logged. |
| Input | Server-side validation on every field; message length ≤ 1000; batch size ≤ 500; schedule ≤ 30 days ahead. |
| Headers | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`; secure cookies when not in debug mode. |
| Deployment surface | In the single-container image only the web server is exposed; `/admin` and the simulator are not reachable from outside. |
| Data | All demo people are fictional and use `example.com` emails. No message ever leaves the simulator. |

---

## 13. Assumptions, limitations, known issues

* **Region.** Mobile numbers are validated as Indian mobiles (`+91`, 10 digits starting 6–9), matching the design's data. Emails are stored lower-cased.
* **Provider.** Both providers are simulated. "Delivered" and "Read" mean the *simulator* confirmed them; no real SMS or email is sent.
* **Worker scale.** The worker loop is meant for one or a few processes (claiming is safe with many). At high volume you would move to a dedicated queue (for example Celery or SQS) and use `SELECT … FOR UPDATE SKIP LOCKED` on PostgreSQL.
* **SQLite** is for local development only (WAL mode handles the API, worker and webhooks writing at once). Use PostgreSQL elsewhere.
* **Updates by polling**, not WebSockets. The UI states the refresh interval.
* **Templates** can be created and used from the Send panel; editing or deleting a template is available via the API only.
* **Simulator rate limiting** is per process, in memory. Run one simulator process.
* **Throttling behind proxies.** On some hosts all users may share one throttle bucket (the client IP comes from `X-Forwarded-For`).
* **Docker on Windows.** On this development machine, Docker Desktop's IPv6 `localhost` forwarding dropped about 20% of connections. Using `http://127.0.0.1:<port>` was 100% reliable. This is a local Docker issue, not an app bug.

---

## 14. Project structure

```
backend/                 Django API
  candidates/            model, validation, selectors (search/filter/annotate), views, tests
  messaging/
    providers/           CommunicationProvider interface, SimuText & SimuMail adapters, registry
    services/            enqueue · dispatch (worker) · status_updates (webhooks) · actions (retry/cancel) · templating
    policy.py            failure categories, recruiter-facing wording, retry rules
    management/commands/ run_worker, seed_demo
    tests/               dispatch, status updates, webhooks/adapter, API
  core/                  error format, pagination, throttling, test helpers
simulator/               SimuText/SimuMail provider service (own DB, API, dispatcher, scenarios, tests)
frontend/                Next.js App Router + MUI
  src/components/        table, dialogs, drawers, history, provider status, notifications
  src/lib/api/           typed API client and endpoints
  e2e/                   Playwright journeys
deploy/                  single-container image (Dockerfile, Procfile, start.sh)
scripts/                 setup_dev.py, dev.py
docs/                    design notes, API reference, manual test checklist, screenshots
```
