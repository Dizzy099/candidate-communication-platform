# Submission: Candidate Communication Platform

**Repository:** https://github.com/Dizzy099/candidate-communication-platform
**Live demo:** _[add the deployed link, or delete this line if submitting the repository only]_

Hi,

Please find my submission for the Candidate Communication Platform assignment.

**What's built.** A full-stack recruiter tool implemented from the supplied Figma design (Next.js, React, TypeScript, Material UI; Django REST Framework). Recruiters can add, search, view and delete candidates, then message one candidate or many at once. Every message is tracked on its own from Queued → Sent → Delivered → Read, and the communication history explains what was sent, when, and why anything failed.

**How delivery works.** Messages go through a separate provider service I built for the assignment (a simulated SMS provider plus an email channel). It runs as its own process with its own database, returns reference IDs, and sends status updates back through signed webhooks. A background worker sends the messages, retries temporary failures automatically within limits, and never blocks one candidate's message on another's failure. Duplicate and out-of-order status updates are handled safely, and a recruiter can retry a failed message only when retrying can actually help.

**Bonus features:** message templates with candidate variables, scheduled messages, multiple providers (SMS and email), provider health with statistics, and retry for failed messages.

**Testing:** 85 backend tests, 18 provider-simulator tests, 17 frontend unit tests, and 7 browser end-to-end tests. All pass, including against PostgreSQL in Docker. The production build succeeds.

**Running it:** two commands (`python scripts/setup_dev.py`, then `python scripts/dev.py`), or `docker compose up --build`. The README has a five-minute demo script, including deterministic test numbers that trigger each failure case.

**Honest limitations:** the providers are simulated, so no real SMS or email is sent. There's no login, since the brief and design don't include one; that decision is documented. Status updates reach the browser by polling every few seconds rather than by push.

Thank you for your time. I'd be glad to walk through the design decisions.

Regards,
Awanish Mishra
