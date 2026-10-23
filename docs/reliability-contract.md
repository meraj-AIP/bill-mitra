# Reliability contract: retries, durable queues, self-healing

Goal: no consumer message, reply, extraction or staff action is lost to a transient failure. Whatever can be retried
is retried automatically, with backoff, for a bounded time; whatever still fails is parked where a person sees it.
Hard rules still hold (no model numbers, number guard, no consumer data in logs, consumers never see staff names).

## 1. One retry policy for every outside call (`app/core/retry.py`)

- `async def call(op, *, attempts, base_s, max_s, budget_s, retry_on)`: exponential backoff with full jitter, honours
  `Retry-After`, stops at the attempt count or the total time budget, whichever first. Never sleeps in tests (the
  sleep function is injectable).
- Retry only transient failures: timeouts, connection errors, HTTP 408, 409 where the provider says retry, 425, 429,
  500, 502, 503, 504. Never 400, 401, 403, 404, 422: those are logged once and surfaced.
- Applied to: Azure OpenAI (vision read, classify, wording, assist), Soniox TTS and STT, WhatsApp Graph (send,
  media upload, media download), DISCOM billing records, DISCOM bills by USC. Each caller keeps its own settings
  (vision: 3 attempts in 60 s; wording and classify: 2 attempts in 15 s, then the rules fallback; WhatsApp send: 3
  attempts in 20 s inline, then the outbox).
- SQLite `database is locked` retried with a short backoff inside `store/db.tx()` (bounded, 5 s).
- Every retry logs one line with the operation name, attempt and status code only.

## 2. Durable inbound queue (build on `store/wa_queue.py`)

- Already in place (other session): the webhook stores each inbound message in `wa_turns` and answers 200 at once;
  `claim(sender)` takes the oldest unclaimed row only when no row of that sender is claimed within a 300 s lease, so
  one sender is never processed by two workers at once; `resume()` at startup. Keep these claim semantics and
  `tests/test_wa_queue.py`. Extend it with attempts, next_attempt_at, last_error and a failed state, as below.
- A failed turn is retried with backoff (1 min, 5 min, 15 min; max 4 attempts). After the first failure the consumer
  gets one neutral line ("We got your message and are working on it; we will reply here shortly"), never twice.
- After the last attempt the job is parked as `failed` and a staff alert `inbound_failed` is raised (no message text
  in the alert). Parked jobs can be retried from the admin Operations page.
- The web chat keeps its direct request path but retries its own provider calls through section 1.

## 3. Durable outbound queue (`store/outbox.py`)

- Every message to a consumer (bot replies, staff replies, requests, reminders, status notes, codes) goes through
  the outbox. A send that fails after the inline retries is queued with backoff (1, 5, 15, 60 minutes, then every 3
  hours) up to 24 hours. Outside the 24 hour WhatsApp window the approved template is used (as notify does today).
- Idempotent: one row per logical message (`dedupe_key`), and a message that Meta accepted (wamid stored) is never
  sent again. The complaint thread shows the delivery state as it changes (queued, sent, failed), and the existing
  "Send again" stays for staff.
- After the final attempt: `failed`, an alert `delivery_failed` to the complaint holder, and the thread shows it.

## 4. Extraction that fails

- A bill photo whose read fails for a transient reason (provider down, timeout, rate limit) is kept and queued as a
  job (`extract_jobs`), retried on the same backoff as section 2. The consumer is told once that the bill is being
  read and will hear back; when the read succeeds, the normal report message is sent (through the outbox). A read
  that fails for a permanent reason (not a bill, unreadable) is answered as today, with no retry.
- The web dashboard upload: when the read fails transiently, the server answers 202 with a job id and the dashboard
  polls it until the report is ready (the bill then appears in My bills).

## 5. Self-checks (scheduler)

- A `sweep_stuck` job every run: requeues claims whose lease expired, outbox rows stuck in sending, extract jobs
  stuck in running. Each requeue audited with actor null.
- `/api/health` adds counts: inbox queued/failed, outbox queued/failed, extract queued/failed, oldest queued age.
- Admin Operations page (perm `audit.view` or `accounts.manage`): the parked failures with Retry and Dismiss, and the
  queue counts. No message bodies shown, only ticket, kind, attempts, last error class, times.

## 6. Frontend

- Queries: retry network and 5xx errors up to 3 times with backoff; never 4xx. Refetch on reconnect and focus.
- Mutations: retry only when safe (idempotent routes or the network failed before the request reached the server),
  never a second send of a reply or a decision; show "Retrying" and a clear "Try again" when it gives up.
- Uploads (bill, consumer photo): retry the upload on network failure with backoff, keep the preview, show progress.
- An offline banner when the browser is offline, and queued actions are not silently dropped.
