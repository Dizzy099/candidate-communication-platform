# Manual test checklist

Start from fresh demo data: run `python scripts/dev.py`, then reset with `seed_demo --reset` (see README §2). Open http://localhost:3000. Tick each box as you go.

## Candidates

- [ ] The list shows 21 demo candidates, 10 per page; "1–10 of 21"; next/last page buttons work.
- [ ] Changing rows per page to 25 shows everyone on one page.
- [ ] Search `kumar` shows only the Kumars; search `98765 43210` finds Krishna; search `A1B2C3` finds Krishna.
- [ ] Search `zzz` shows "No matching candidates"; **Clear search and filters** resets.
- [ ] Status header icon → tick *Failed* → only Urvashi (and any new failures); *Never messaged* → candidates showing NA.
- [ ] Name header icon → *Sort Z → A* reorders; *Default order* restores.
- [ ] **Add candidate**: the button stays disabled until all three fields have text.
- [ ] Mobile `12345` → "Enter a valid 10-digit Indian mobile number…"; email `abc` → "Enter a valid email address…".
- [ ] Mobile `09876543210` (Krishna's number in another format) → "already exists: Krishna Khandelwal (A1B2C3)".
- [ ] A valid new candidate → toast "‹Name› added successfully", row at the top, Last message "NA".
- [ ] Select 1 candidate → **Delete candidate** → dialog names them → confirm → "Candidate deleted successfully".
- [ ] Select 3 → Delete → "Are you sure you want to delete 3 Candidates?" → "3 Candidates deleted successfully".

## Messaging

- [ ] With nothing selected, **Delete** and **Send message** are disabled.
- [ ] Select one normal candidate → Send → "1 Recipient" chip → type → **Send message** → toast "Sending to …" then "Message sent to ‹Name›".
- [ ] Within about 10 s the row's status goes Sent → Delivered → Read (refreshes every 4 s; caption shows the last update).
- [ ] Double-clicking **Send** never creates two messages (check the history: one entry).
- [ ] Select 10+ candidates → recipient chips use at most two lines, then "+ n" (hover shows the rest).
- [ ] Bulk to Rohit (000), Neha Joshi (111), Pooja (666), Deepa (333), Sneha → confirm dialog shows the count → toast counts progress → "Message sent to 2 of 5 candidates. 3 failed."
- [ ] **View details**: Rohit "Invalid mobile number", no Retry; Pooja and Deepa have Retry; Neha recovered automatically.
- [ ] **Retry 2 failed** → both become Sent → Delivered → Read.
- [ ] Template: choose *Interview reminder* → text filled → each candidate gets their own first name (check two histories).
- [ ] Type `{{nickname}}` and send → inline error "Unknown variable(s): nickname…".
- [ ] More than 1000 characters → counter turns red and Send is disabled.
- [ ] **Save as template** → name it → it appears in the template list.
- [ ] Send via **Email · SimuMail** → history shows "| Email"; a candidate whose email contains "bounce" fails with "Invalid email address".
- [ ] **Schedule for later** (+2 min) → toast "Message scheduled…" → history shows Scheduled with **Cancel**; leave one to send itself when due; cancel another.

## History

- [ ] Click any name (underlined on hover) → drawer with Candidate ID, name, phone, email.
- [ ] Ira Akbar → "No communication history" with the illustration.
- [ ] Messages newest first; each shows date | time | channel and a status chip.
- [ ] A failed message explains the reason; **Details** shows provider reference, attempts, technical detail and the timeline.
- [ ] Arjun Nair (555): after sending, Details shows the out-of-order 'delivered' marked as ignored, and the status stays Read.
- [ ] **Send message** in the history drawer opens the Send panel for that candidate.

## Provider and failures

- [ ] Header pill: "Simulated providers · Operational"; the popover lists SMS and Email, stats and test numbers.
- [ ] Switch on **Simulate provider outage** → pill turns red; sending shows Retrying · "Messaging service unavailable".
- [ ] Turn the outage off within about 20 s → the message recovers automatically; leave it on → Failed with Retry → turn off → Retry → Read.
- [ ] Stop the simulator process (Ctrl+C everything, restart without it) → pill shows Unavailable; sends retry, then fail with a clear reason; the app never shows a raw error.
- [ ] Stop the API (keep the web server running) → the list shows "The server is temporarily unreachable…" with **Try again** instead of crashing; start it again and click Try again.

## Responsive

- [ ] At a narrow window (about 400 px) the header wraps, the table scrolls sideways, and the drawers go full-width.
