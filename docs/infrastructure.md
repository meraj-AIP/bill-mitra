# Infrastructure and capacity

How Bill Mitra should run on GCP for 20,000 to 40,000 complaints a day, what limits the current build, and the order
in which to change it. Measured numbers come from a load test on a laptop against a seeded copy of the database
(section 3). Treat them as relative, not as a promise for any particular machine.

## 1. The load we plan for

| | Average | Peak (10x, morning and bill day) |
| --- | --- | --- |
| Complaints a day | 20,000 to 40,000 | |
| WhatsApp messages in (about 7 to 15 per complaint, plus Meta's delivery statuses) | 200,000 to 800,000 a day, 2 to 9 a second | 25 to 95 a second |
| Messages out to Meta | about the same | about the same |
| Staff online | 300, two tabs each | 600 |
| Staff requests (screens refresh on their own) | about 10 a second | about 30 a second |
| Model calls (bill reading, wording, AI brief) | 1 to 3 per complaint | provider rate limits matter |

Growth per day at 30,000 complaints, measured on synthetic rows of the real schema:

| Data | Per day | Kept |
| --- | --- | --- |
| Chat history | about 200 MB | retention_days (180) |
| Events for the console | about 70 MB | not pruned yet |
| Bills | 60 to 120 MB | retention_days, unless a complaint points at it |
| Complaint messages, complaints, audit log, alerts | about 60 MB | not pruned |
| Media (bill photos, voice notes, voice replies) | about 8 GB | retention_days, complaint photos longer |

So the database grows about 0.5 to 1 GB a day and media about 8 GB a day. Media must live in object storage, not on
the VM disk.

## 2. What was fixed in this round

| Problem found | Change |
| --- | --- |
| Every message to Meta built a new HTTPS client: about 30 ms of CPU each, capping a worker near 12 messages a second | One pooled client per provider (`app/services/http.py`), used for WhatsApp and OpenAI |
| A person's quick taps were handled at the same time and out of order, breaking the complaint chat; turns in flight were lost on restart | A shared queue table (`store/wa_queue.py`): a worker takes a sender's oldest waiting message only when no worker is handling one of theirs, so order holds across all workers; waiting turns are picked up again at start; a cap on turns running at once (`WHATSAPP_TURN_CONCURRENCY`) |
| The console summary took 8 to 21 s and every open console asked for it every 15 s | Cached for 60 s per window and DISCOM, shared by everyone; the screen refreshes every 2 minutes |
| The inbox computed 9 lookups for every complaint before sorting | Tickets for the page are picked first, the lookups run for those only |
| 17 missing indexes (events, complaints, messages, media, audit log, retention) | Created at startup (`store/db.py` `_PERF_INDEXES`) |
| SQLite waited on nothing and synced every statement | `busy_timeout`, `synchronous=NORMAL`, larger page cache |
| Any page number was accepted, deep pages took seconds | Page numbers capped at 1000 on every list; search and filters reach older rows |
| The retention sweep ran only at startup | Also a daily scheduled job |
| The overdue job picked the same oldest 100 cases every run; the digest recounted every 15 minutes | Already alerted cases are skipped; the digest skips anyone who already has today's |
| About 0.5 to 0.7 GB of logs a day, no rotation | httpx at WARNING, uvicorn access log off (nginx keeps one), Docker log size capped |
| Hashed web assets had no cache header | One year, immutable; `index.html` is checked every time |
| Screens refreshed every 15 to 30 s | 60 to 120 s; actions on a screen still update it at once |
| With several workers, every worker ran the automation jobs | A file lock lets exactly one worker on the host run them (`services/scheduler.py`) |
| A request could wait 9.5 s while the summary was rebuilt | After the first build the last answer is served at once while one thread builds the next |
| The write ahead log grew to hundreds of MB | A daily checkpoint and `PRAGMA optimize` (`db.maintain`) |
| A lost DISCOM tap crashed the complaint chat | It asks for the DISCOM again |

## 3. Measured capacity

Load test on a laptop with a seeded copy of the database: 300,000 complaints, 900,000 complaint messages, 2 million
events and 1 million chat rows. AI keys off, Meta replaced by a local fake, so this measures Bill Mitra itself.
Webhook load is 7 message complaint journeys, each from its own number.

**WhatsApp webhook, one worker, no staff using the console**

| Messages a second | Errors before | Errors after | p95 latency before | p95 after | Complaints completed before | after |
| --- | --- | --- | --- | --- | --- | --- |
| 20 | 0% | 0% | 7.8 s | 7 ms | 173 of 173 | 173 of 173 |
| 50 | 50% | 0% | 14.4 s | 9 ms | 60 of 430 | 430 of 430 |
| 100 | 75% | 0% | 13.7 s | 12 ms | 15 of 859 | 859 of 859 |

At 100 messages a second one worker delivered about 90 a second with no backlog, using about a quarter of a core.

**Staff console, one worker**

| Staff at once | Requests a second before | after | Errors before | after |
| --- | --- | --- | --- | --- |
| 10 | 0.6 | 6.7 | 0% | 0% |
| 50 | 0.9 | 5.3 | 39% | 0% |
| 100 | 1.0 | 6.1 | 70% | 0% |

**Both together: 20 messages a second plus 50 staff for 2 minutes**

| | 1 worker before | 1 worker after | 4 workers before | 4 workers after |
| --- | --- | --- | --- | --- |
| Webhook errors | 67% | 46% | 20% | **0%** |
| Webhook p95 | 60 s | 55 s | 23 s | **10 ms** |
| Complaints completed | 19 of 344 | 82 of 344 | 167 of 344 | **343 of 344** |
| Console errors | 97% | 0% | 11% | **0%** |
| Console requests a second | 3.2 | 5.8 | 1.9 | **10.7** |
| Peak memory | 215 MB | 242 MB | 771 MB | 804 MB |

What this means for the target:

- One worker now carries far more WhatsApp traffic than the 800,000 messages a day peak (about 93 a second), as long
  as the console is quiet.
- With staff working, run **4 workers** on the current VM. That passed the mixed test with no errors and covers
  20,000 to 40,000 complaints a day at the average rate. A 93 messages a second peak together with heavy console use
  was not tested on this setup; that is what the GCP layout in section 5 is for.
- The console is now the ceiling, at about 10 requests a second across all staff on 4 workers, because its SQL runs
  on the event loop (section 4).

**The same mixed test on Postgres** (4 workers, the same 300,000 complaint copy moved over with
`app.tools.sqlite_to_postgres`, Postgres 17 on the same laptop):

| | SQLite, 4 workers | Postgres, 4 workers |
| --- | --- | --- |
| Webhook errors | 0% | 0% |
| Webhook p95 | 2.9 s | 1.1 s |
| Webhook max | 14.5 s | 3.1 s |
| Complaints completed | 344 of 344 | 344 of 344 |
| Console requests a second | 15.1 | 20.3 |
| Console p95 | 12.0 s | 6.7 s |
| Console errors | 0% | 0% |

Read handlers now run in FastAPI's thread pool (`def`, not `async def`), so on Postgres several console queries run
at once instead of one after another on the event loop. What is left are the two heaviest queries, the priority
sorted complaint list and the 30 day daily chart. Each takes about a second on its own and several seconds when many
run at once on the same machine as the load generator. Keyset pagination and the daily rollup (section 7) fix both.

The scripts are kept outside the repo; rerun the same journeys after each step in section 7.

## 4. What still limits a single server

1. **Writes and the WhatsApp turn still run SQL on the event loop.** Read handlers moved to the thread pool; on
   SQLite they still take turns on one connection, on Postgres each gets its own pooled connection. The app runs on
   Postgres when `DATABASE_URL` is set (docs/decisions/0001-postgres-store.md).
2. **The WhatsApp queue lives in SQLite on one host.** It keeps order across workers and survives restarts, but it
   cannot be shared by several servers. Pub/Sub with an ordering key per sender replaces it on GCP (section 5).
3. **Several processes share little.** Four workers on SQLite work well (no lock errors in the test) and the
   automation now runs in one of them only. Each still keeps its own login rate limits and its own per-ticket AI
   brief lock, so a limit is effectively four times looser and two workers can rarely make the same first AI call.
   Redis fixes both when the app moves to GCP.
4. **Console counts scan events.** The 60 second cache hides this. At a year of data, replace it with a daily
   rollup table written by the scheduler.

## 5. Target architecture on GCP

Everything in `asia-south1` (Mumbai) so data stays in India, with backups copied to `asia-south2` (Delhi).

```
                 Meta WhatsApp Cloud API            Staff and consumers (browser)
                          |                                    |
                          v                                    v
             External HTTPS Load Balancer + Cloud Armor (WAF, rate limits per IP)
                 |                         |                              |
       /api/whatsapp/webhook          /api/*                       static web app
                 |                         |                              |
                 v                         v                              v
      Cloud Run "ingest"          Cloud Run "api"                 Cloud Storage + Cloud CDN
      (verify signature,          (console, review, web chat,     (hashed assets cached a year)
       dedupe, publish, 200)       admin; 2 to 20 instances)
                 |                         |
                 v                         |
      Pub/Sub topic, ordering key = sender |
                 |                         |
                 v                         v
      Cloud Run "turns" worker  ---->  Cloud SQL Postgres (regional HA, private IP)
      (one turn at a time per sender,      + read replica for console counts
       calls OpenAI, Sarvam, Soniox,   Memorystore Redis (rate limits, shared caches, AI brief lock)
       sends replies via Meta)         Cloud Storage bucket for media (lifecycle rules, signed URLs)
                 |
       Cloud Scheduler -> Cloud Run job "automation" (reminders, overdue, digest, retention), exactly one runner
```

Why each piece:

| Piece | Why |
| --- | --- |
| Load balancer + Cloud Armor | One TLS entry point, WAF rules, per IP rate limits before traffic reaches the app, and real client IPs |
| Cloud Run for ingest, api and turns | Scales on load and to the minimum at night; each piece scales on its own. Keep at least 1 instance warm for ingest and api so Meta never waits on a cold start |
| Pub/Sub with ordering by sender | The webhook answers Meta in milliseconds whatever the backlog; one sender's messages are handled in order; nothing is lost on a deploy |
| Cloud SQL Postgres | Concurrent reads and writes, point in time recovery, automatic backups, a replica for heavy counts. Use the Cloud SQL connector or PgBouncer, pool size about 10 per instance |
| Memorystore Redis | State shared by all instances: login rate limits, the 60 s console cache, the AI brief "one call per ticket" lock |
| Cloud Storage for media | 8 GB a day does not belong on a VM disk. Lifecycle: Nearline after 30 days, delete at retention; complaint evidence in a separate prefix kept longer |
| Cloud Scheduler + one Cloud Run job | The automation jobs run once, not once per instance |
| Secret Manager | WhatsApp, OpenAI, Sarvam and Soniox keys out of `.env` files |
| Cloud NAT with a static IP | Outbound calls to DISCOM billing APIs come from one address they can allow list |

Sizing to start with:

| Service | Start | Notes |
| --- | --- | --- |
| ingest | 1 to 10 instances, 1 vCPU, 512 MB, concurrency 80 | Light: verify, dedupe, publish |
| turns | 2 to 30 instances, 1 vCPU, 1 GB, concurrency 20 | Mostly waits on providers; image work needs the memory |
| api | 2 to 20 instances, 1 vCPU, 1 GB, concurrency 40 | |
| Cloud SQL | 4 vCPU, 16 GB, 500 GB SSD with auto growth, HA | Watch CPU and connections; add a read replica when console counts move off the cache |
| Redis | Basic 1 GB, then Standard for HA | |

## 6. Running safely

| Area | Practice |
| --- | --- |
| Logs | Structured JSON to Cloud Logging. Exclusion filters for health checks and successful webhook posts. No message text, phone numbers or tokens in logs (the code already masks service numbers and hashes phone numbers) |
| Metrics and alerts | Webhook latency p95 over 1 s, turn backlog (Pub/Sub oldest unacked message) over 2 minutes, provider error rate over 5%, number guard fallbacks, Cloud SQL CPU over 70%, 5xx rate over 1% |
| Uptime | Uptime check on `/api/health` from three regions. Keep `/api/health` free of database work so it stays cheap |
| Deploys | Cloud Run revisions with traffic splitting: 10% first, then 100%. Database migrations run once as a job before the new revision gets traffic |
| Backups | Cloud SQL automated backups with point in time recovery, plus a nightly export to a Delhi bucket. Media bucket with object versioning for 7 days |
| Security | Webhook signature required (it is now), Cloud Armor in front, private IP for the database, least privilege service accounts, VAPT before go live |
| Cost control | Scale to small at night, media lifecycle rules, log exclusions, budget alerts |

## 7. Order of work

1. **Now, on the current VM:** the fixes in section 2. In the VM's compose file, run
   `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --no-access-log --proxy-headers
   --forwarded-allow-ips *`, keep the 127.0.0.1 port binding, raise `mem_limit` from 1g to 2g (four workers peaked
   at about 0.8 GB under load), and add log rotation (`logging: max-size 20m, max-file 5`). Turn on gzip in nginx for
   `text/*`, `application/javascript` and `application/json`. Copy the nightly backups to a GCS bucket.
2. **Before the pilot grows:** media to Cloud Storage; Postgres on Cloud SQL; Redis for rate limits and caches.
   Moving to Postgres needs no code change:
   1. Create the database with C collation, so text sorts byte by byte as it does in SQLite:
      `CREATE DATABASE billmitra TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'`.
   2. Stop the app and copy the data once:
      `DATABASE_URL=postgresql://... python -m app.tools.sqlite_to_postgres var/billmitra.db`. It refuses a database
      that already holds accounts, complaints, bills or events, and copies everything in one transaction.
   3. Set `DATABASE_URL` (and `DATABASE_POOL_SIZE`, 10 per worker by default; workers times pool size must stay
      under the server's `max_connections`) and start the app. Keep the SQLite file until the new setup has run
      for a week.
3. **For full scale:** the ingest service with Pub/Sub, the turns worker, the scheduler as one Cloud Run job, the
   load balancer with Cloud Armor, and the static app on Cloud Storage with Cloud CDN.
4. **Then:** a daily rollup for console counts, keyset pagination for very deep lists, and retention for events,
   alerts and the audit log agreed with the DISCOM.

Run the load test again after each step (scripts and method in section 3).
