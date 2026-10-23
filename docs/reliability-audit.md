# Reliability audit: every outside call and every step that can fail for a passing reason

Audited against docs/reliability-contract.md sections 1 to 5. "Before" is the code as it stood; "after" is what it
does now. Retry policies live with each caller and all run through `app/core/retry.py` (full jitter, Retry-After,
attempt count and time budget, transient failures only: timeouts, connection, read and protocol errors including a
pooled connection the far end closed, HTTP 408, 425, 429, 500, 502, 503, 504).

| Operation | What can fail | Before | After |
| --- | --- | --- | --- |
| Vision read: classify, read, reread (`services/vision.py` via `openai_client.chat_json`) | timeout, reset connection, 429, 5xx, malformed answer | own loop: 3 tries on 408/429/5xx only, no jitter, no budget; then the consumer was asked to type the units and the dashboard said "try again in a minute" | `READ` 3 tries in 60 s per call. A failure still transient after that becomes an extract job (row below); a malformed answer is permanent and answered as before |
| Wording, classify, explain, assist (`services/llm.py`) | as above | same loop, waits up to 20 s each | `TEXT` 2 tries in 15 s, then the checked template or the rules, as before |
| Soniox TTS (`services/soniox_tts.py`) | timeout, 429, 5xx | one try, then text | `VOICE` 2 tries in 15 s, then text |
| Soniox STT: upload, create, poll, transcript (`services/stt.py`) | timeout, 429, 5xx | one try each, then "please type" | `LISTEN` 3 tries in 15 s per request, then "please type" |
| WhatsApp media download (`channels/whatsapp/client.py`) | Meta down, reset connection, 404, too large | one try; any failure told the consumer "send it again" | `MEDIA` 3 tries in 20 s. Transient: the whole turn fails and the inbox retries it. Permanent (404, too large): "send it again" as before |
| WhatsApp media upload (voice note, chart) | as above | one try; a failure broke the rest of the turn | `MEDIA` 3 tries in 20 s, inside the outbox send, so a failure queues the message |
| WhatsApp send: bot replies in a turn | Meta down, 5xx, reset pooled connection (the lost message in the load test) | one try; the error escaped the turn, the rest of the replies were lost | every message goes through the outbox with key `turn:<wamid>:<n>`: `SEND` 3 tries in 20 s inline, then queued 1, 5, 15, 60 minutes, then every 3 hours, up to 24 hours. Messages to one person keep their order. A retried turn never sends a message twice |
| WhatsApp send: staff reply, status line, requests, reminders, notices (`services/notify.py`) | as above, plus outside the 24 hour window | one try; a 4xx fell back to the template, a timeout was marked failed with "Send again" | through the outbox. Thread shows `queued`, then `sent` or `failed`. The template goes straight away when the consumer last wrote over 24 hours ago, and still on a refused free text. Final failure raises `delivery_failed` to the holder. "Send again" still works on `failed` |
| One-time code template | as above | one try | outbox row for the record and dedupe, `SEND` inline only. The number and the code are never stored, so a code that fails is not queued; the consumer asks again |
| Late failure reported by Meta (status webhook) | message accepted, then not delivered | template resent directly, outside any retry | the template goes through the outbox (key `window:<wamid>`) and updates the thread |
| Mark read | as above | one try, ignored | unchanged: one try, ignored |
| DISCOM billing records (`services/billing_records.py`) | timeout, 5xx | one try, then "missing" | `LOOKUP` 3 tries in 20 s, then "missing" |
| DISCOM bill and contact by USC (`services/discom_bills.py`) | timeout, 5xx | one try, then "not found" | `LOOKUP` 3 tries in 10 s, then "not found"; 404 is an answer, not an error |
| Inbound WhatsApp turn (`store/wa_queue.py`, `router.drain`) | any of the above, a locked database, a bug | error logged and the row deleted: the message was lost (or answered "something went wrong, try again") | the turn raises to the inbox: retried after 1, 5 and 15 minutes, 4 tries. After the first failure the consumer gets one neutral line. Then parked as `failed` with an `inbound_failed` alert (no text). The sender's later messages wait behind a retry and go ahead once it is parked. Claim semantics unchanged |
| Worker dies mid turn | process killed | the lease was taken over only when the same sender wrote again or the server restarted | `sweep_stuck` releases expired leases every run and `retry_inbox` drains them, audited with no actor |
| Bill read on WhatsApp while the reader is down (`flows/bill.py`) | transient provider failure after `READ` | asked to type the units | `extract_jobs` row, the consumer told once that the bill is being read, retried 1, 5, 15 minutes; on success the normal report goes through the outbox. On the last try a failure asks for the units as before and the job is parked |
| Dashboard upload while the reader is down (`flows/report.py`, `POST /api/bills`) | as above | 200 with `reading_failed` | 202 with a job, `GET /api/bills/jobs/{id}` to poll; when read, the bill is in My bills |
| Outbox row or extract job whose worker died | process killed mid send or read | not applicable | `sweep_stuck` puts `sending` rows (lease 2 minutes) and `running` jobs (lease 10 minutes) back, audited |
| SQLite transaction (`store/db.tx`) | another worker holds the write lock | `busy_timeout` 5 s | unchanged for reads and ordinary writes: a deferred transaction, so a read never takes the write lock and a write waits up to 5 s inside SQLite (no sleep loop on the event loop). `tx(immediate=True)` takes the write lock up front only on the short claim paths: inbox add, claim, done and fail, outbox claim, extract job claim. (A first version took it on every transaction; the load test showed it serialised reads behind writers, so it was reverted.) |
| Startup with several workers on a fresh database | the workers race in schema creation and migration, then a finished worker's startup writes meet another's migration; two workers seeding the same sample accounts | 3 of 4 workers died with "locked" | `db.startup_lock()`, a blocking `flock` on `data_dir/migrate.lock`, covers schema, migration, upgrade and every startup write (bootstrap admin, sample accounts, mock purge, retention sweep, inbox resume), with a 30 s busy timeout while it is held. Later workers find the work done. The scheduler starts after the worker's turn |
| Scheduler | a job raises | one failing job did not stop the others | unchanged, plus a second loop every `QUEUE_INTERVAL_SECONDS` (30) for `sweep_stuck`, inbox, outbox and extract jobs, on the same worker lock |
| Web chat | provider calls | direct, failures answered at once | still direct; provider calls retry through the policies above; a bill read that still fails asks for the units |

## What staff see

- `GET /api/health` adds queue counts. `GET /api/admin/operations` lists parked items (ticket, kind, attempts, last
  error class, times; never a body or a number) with Retry and Dismiss, both audited.
- Alerts: `inbound_failed` (global accounts with `audit.view`), `delivery_failed` (the complaint's holder, or its unit
  with `complaints.reply`).

## Known limits

- Meta has no idempotency key. A send that timed out after Meta took it can still reach the consumer twice when it is
  retried; a message with a stored `wamid` is never sent again.
- A turn that failed half way runs again from the start. Messages it already sent are not sent again, but other side
  effects of the first try (a chat history line for a bot message, a complaint recorded) can repeat.
- Parked rows keep the number and the message until someone retries or dismisses them, or the person sends STOP.
