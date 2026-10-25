# Implementation checklist

Legend: ✅ done and verified · 🟡 done, partly verified · ⛔ blocked (external) · ✖ not done

## Assignment requirements

| # | Requirement (from the assignment) | Status | Evidence |
|---|---|---|---|
| 1 | Add candidate (name, phone, email) | ✅ | API tests; e2e "add a candidate…" |
| 2 | View all candidates | ✅ | API + e2e |
| 3 | Search candidates | ✅ | API test (name/phone/email/code); e2e search |
| 4 | View candidate details | ✅ | History drawer header; `GET /candidates/{id}` test |
| 5 | Send a message to one candidate via a provider | ✅ | dispatch tests; e2e single send |
| 6 | Record the communication and its status | ✅ | Message, attempt and event models; tests |
| 7 | Bulk messaging, independent per candidate | ✅ | `test_bulk_send_tracks_each_recipient_independently`; e2e bulk |
| 8 | One failure doesn't block the others | ✅ | `test_unexpected_exception_fails_one_message_without_stopping_others` |
| 9 | Status reflects the latest provider information | ✅ | Webhook tests; e2e watches Sent→Read |
| 10 | Provider: send, reference ID, status updates, success, failure, temporary failure | ✅ | Simulator tests and live runs |
| 11 | Provider is separate from the main app | ✅ | `simulator/`: own process, DB, HTTP API |
| 12 | Duplicate status updates handled | ✅ | `test_duplicate_event_is_acknowledged_but_not_reapplied`; scenario 555 live |
| 13 | Invalid recipient, temporary failure, rate limit, delivery failure, unavailable, other | ✅ | `test_error_classification`; scenarios 000–777; outage switch verified live |
| 14 | Meaningful messages, not raw errors | ✅ | `policy.py` copy; `test_unhandled_errors_do_not_leak_details` |
| 15 | Communication history (what, when, status, failure reason) | ✅ | History drawer; API test |
| 16 | UX states: loading, sending, empty list, empty history, failed requests, failed messages, updating statuses, bulk results | ✅ | Screenshots in `docs/screenshots`; e2e |

## Bonus

| Bonus | Status | Evidence |
|---|---|---|
| A. Templates with candidate variables | ✅ | Template API tests; variable rendering test |
| B. Scheduled messages | ✅ | `test_scheduled_message_waits_until_due`, cancel test |
| C. Multiple providers | ✅ | `MultipleProviderTests`; e2e email test |
| D. Provider health | ✅ | `ProviderApiTests`; header popover |
| E. Retry failed messages (retryable vs permanent) | ✅ | Retry API tests; e2e retry |

## Engineering

| Item | Status | Notes |
|---|---|---|
| Next.js + React + TypeScript + MUI; Django + DRF | ✅ | |
| Figma investigated and implemented | ✅ | Decoded `.fig`; see `docs/DESIGN_NOTES.md` |
| Migrations, seed and reset commands | ✅ | `migrate`, `seed_demo [--reset]` |
| Idempotency (double submit, provider retries) | ✅ | client_request_id tests; Idempotency-Key reuse test |
| No long transactions across provider calls | ✅ | Worker design; claim/lease tests |
| Webhook signature verification | ✅ | Signature tests |
| Backend tests | ✅ | 85 passing (SQLite and PostgreSQL) |
| Simulator tests | ✅ | 18 passing |
| Frontend typecheck, lint, unit tests, build | ✅ | Clean; 17 passing; build OK |
| End-to-end browser tests | ✅ | 7 passing on dev, Compose/PostgreSQL, single-container and the live Render site |
| Docker Compose (PostgreSQL) | ✅ | Built and run locally |
| Single-container deploy image | ✅ | Built and run locally; e2e passed |
| README, API docs, manual checklist | ✅ | |
| GitHub repository pushed | ✅ | https://github.com/Dizzy099/candidate-communication-platform |
| Public deployment | ✅ | https://candidate-communication-platform.onrender.com: all 7 browser tests passed against it |
| Authentication | ✖ | Out of scope by decision (README §12) |
| Template edit/delete UI | ✖ | API supports it; UI covers create and use |
