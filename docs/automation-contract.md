# Automation contract

The automation pack: work the system now does by itself so AEs, managers and consumers chase less.
Rules that still hold: the engine produces every number, consumers never learn who checks their bill,
every automatic action is audited with actor null and shows as System on the case timeline.

Ownership while this is built: backend A (misread, drafts, unmapped suggestions, staff import), backend B
(scheduler, alerts, reminders, escalation, digest, auto applied, patterns), frontend C (all screens), ops D
(health, backups, watchdog, CI). Shared files (`store/db.py`, the four lang files, `config.py`, `api/review.py`):
small targeted edits only, re-read on a failed edit, never rewrite them whole.

## 1. Misread found from the next bill (A)

The strongest evidence of a misread: the next month's bill prints a previous reading lower than the present
reading of the month before. The meter cannot run backwards, so the earlier present reading was too high.

- `app/flows/misread.py`, called after any checked bill is saved (web upload and chat photo) and when a
  wrong_reading case opens.
- Pair: same `user_id`, same service number, bill months M and M+1. Signal when
  `next.previous_reading < earlier.present_reading` and `next.previous_reading >= earlier.previous_reading`.
- Result stored in table `case_suggestions(ticket TEXT PRIMARY KEY, kind TEXT, corrected_present_reading INTEGER,
  source_bill_id TEXT, created_at TEXT)` when a wrong_reading case exists (or later opens) for the earlier bill.
  Audited `case.suggestion` (actor null). An alert `misread_found` goes to the case's section (see 4).
- No case open for the earlier bill: the new bill's report carries
  `misread: {earlier_bill_id, earlier_month: "YYYY-MM", printed_present, next_previous} | null`
  on `BillReport` so the dashboard can offer "Report the {month} bill". Readings are printed values; no money here.

## 2. Pre-filled decision (A)

`GET /api/review/cases/{ticket}/draft` (perm `cases.decide`, in scope) returns `Draft | null`:

```
Draft {
  kind: "correct" | "corrected_reading"
  corrected_present_reading: int | null
  reason_code: ReasonCode
  note: str                      # template text, 20+ characters, no model wording
  evidence: [{kind: "bill" | "message", id: str}]
  strength: "strong" | "likely"
  why: [str]                     # one line per rule that fired, plain English
  preview: Preview | null        # the engine preview for a corrected reading, same shape as the existing preview route
}
```

- Misread suggestion present: `corrected_reading`, reason `photo_misread`, evidence = this bill + the next bill,
  strength `strong`.
- Otherwise clear correct (every line verified, no spike, readings and billing days consistent, nothing asked
  of the consumer still open): `correct`, reason `bill_correct`, evidence = this bill, strength `likely`.
- Otherwise `null`. The AE still records the decision; nothing is decided automatically.

## 3. Unmapped section suggestions and staff import (A)

- `Unmapped` gains `suggestions: [{section_id, name, score}]` (top 3, score 0 to 1, same DISCOM, difflib ratio on
  normalised name and aliases, only score >= 0.8, since different places sharing a suffix score near 0.65).
- `POST /api/admin/accounts/import` (perm `accounts.manage`), multipart CSV, header
  `name,login,role,unit_code`, max 1 MB and 500 rows. Each row: role must exist and not be consumer, unit must be in
  the importer's scope, login unique. Response
  `{created: [{line, login, name, role, unit, password}], errors: [{line, detail}]}`. Passwords are random,
  shown once in this response, never logged or audited. Audit `account.import` with counts only.

## 4. Alerts (B)

Tables: `alerts(id INTEGER PRIMARY KEY, kind TEXT, unit_id TEXT, account_id TEXT, ticket TEXT, title TEXT, body TEXT,
perm TEXT, dedupe_key TEXT UNIQUE, created_at TEXT)` and `alert_reads(alert_id INTEGER, account_id TEXT,
PRIMARY KEY (alert_id, account_id))`.

An account sees an alert when `account_id` is theirs, or when `account_id` is null, the unit is in their scope and
they hold `perm`. Kinds: `misread_found`, `case_overdue`, `case_escalated`, `digest`, `applied_auto`,
`pattern_section`, `request_reminded`, `request_lapsed`.

`app/store/alerts.py` exposes `raise_alert(kind, unit_id, title, body, perm, dedupe_key, ticket=None,
account_id=None) -> bool` (False when the dedupe key exists). A uses it for `misread_found`.

API (any signed-in staff account; consumers get 403):
- `GET /api/alerts?page=1&page_size=20&unread=true` -> `{items: [{id, kind, title, body, ticket, unit_name,
  created_at, read}], total, unread}`
- `POST /api/alerts/{id}/read` -> 204, `POST /api/alerts/read-all` -> 204

## 5. Scheduler and jobs (B)

- `app/services/scheduler.py`: one asyncio task started in the app lifespan when `AUTOMATION_ENABLED` (default
  true; tests set it false). Runs every `AUTOMATION_INTERVAL_SECONDS` (default 900). One failing job is logged and
  never stops the others. Jobs live in `app/flows/automation.py`, each `run_x(now: datetime) -> int` (how many
  things it did) so tests call them with a fixed clock.
- Settings: `REMINDER_AFTER_DAYS=3`, `LAPSE_AFTER_DAYS=7`, `DIGEST_HOUR_IST=8`, `PATTERN_WINDOW_DAYS=90`,
  `PATTERN_MIN_CASES=3`.
- Jobs:
  - consumer reminder: system request for earlier bills open `REMINDER_AFTER_DAYS` -> one reminder message in the
    consumer's language (lang key `request_reminder`), audit `case.remind`, timeline "Reminded the consumer".
  - lapse: open `LAPSE_AFTER_DAYS` -> request closed as answered with the note "No reply; checked with what is on
    file", consumer told neutrally (lang key `request_lapsed`), audit `case.lapse`.
  - overdue: case open longer than its DISCOM's `decision_sla_days` with no decision -> alert `case_overdue` to the
    section (perm `cases.decide`); one more SLA period later -> `case_escalated` to the division above the section
    (perm `cases.view`), `complaints.escalated_at` set, audit `case.escalate`.
  - digest: once a day after `DIGEST_HOUR_IST`, per account holding `cases.decide` with open cases in scope: one
    `digest` alert (account_id set) with counts: awaiting, due today, overdue.
  - auto applied: when the billing records connector is live, for approved revisions still pending update, refetch
    the records; a month entry with `billed_amount` within 1 rupee of the revised amount marks the revision applied
    (actor null), audit `revision.applied_auto`, alert `applied_auto`. Records gain optional `billed_amount`.
  - patterns: per section, approved `corrected_reading` decisions in the last `PATTERN_WINDOW_DAYS` >=
    `PATTERN_MIN_CASES` -> `pattern_section` alert to the division (perm `cases.view`), dedupe per section per month.
- Health: `GET /api/health` gains `automation: {enabled, last_run_at, last_error}`; no personal data.

## 6. Frontend (C)

- Alerts bell in the app bar for staff with the unread count, a popover of the latest 5, and an Alerts page
  (`/alerts`, paged, unread filter in the URL). Each alert links to its case when it has a ticket.
- Case page: a "Suggested decision" card above the decision panel when the draft exists, with the why lines and
  "Use this" which fills the decision form (the AE still records it).
- Dashboard bill report: when `misread` is present, a calm note and a button to report the earlier month.
- Units page: unmapped names show suggestions with one-click "Map to {name}".
- Accounts page: "Import from CSV" with a template download, a results table, and the one-time passwords shown once
  with a copy and download as CSV, warning they will not be shown again.

## 7. Ops (D)

- Docker `HEALTHCHECK` on `/api/health`; compose healthcheck and `restart: unless-stopped`.
- `deploy/backup.sh`: SQLite online backup plus media tar, kept 14 days, optional copy to `BACKUP_BUCKET` with
  gsutil when set. `deploy/watchdog.sh`: three failed health checks in a row restarts the container and logs it.
  Both run from cron on the VM; install steps in `deploy/README.md`.
- GitHub Actions: `ci.yml` (pytest, ruff, typecheck, lint, build on push and PR), `uptime.yml` (every 15 minutes,
  fails when the live health check fails, so GitHub notifies the owner), `deploy.yml` (manual or on main after CI,
  SSH deploy only when the `DEPLOY_*` secrets exist).

## 8. Approvals: the system prepares, an officer approves

Routine work that an officer does the same way every time is prepared by the rules and waits on the Approvals tab.
Nothing reaches a consumer and nothing is decided until a person approves it. Code: `app/flows/proposals.py`
(what to propose), `app/api/proposals.py` (approve, reject, batch), `app/store/proposals.py`.

| Kind | Proposed when | Approving does | Needs |
| --- | --- | --- | --- |
| `explain_correct` | A bill complaint on WhatsApp or the web, every line matches the tariff, the meter was read, no officer has written yet, nothing is being waited for | Sends the checked explanation and resolves the complaint | `complaints.reply` |
| `request_bill` | A bill complaint came without a bill and the bill was never asked for | Asks the consumer for a photo of the bill | `complaints.reply` |
| `request_meter` | The bill's meter status says the reading was estimated and no meter photo was asked for | Asks the consumer for a photo of the meter | `complaints.reply` |
| `decide_correct` | A reading check where the pre-filled decision (section 2) says the bill is correct, and no misread was found | Records "bill correct" in the approver's name, tells the consumer, closes the case | `cases.decide` |

Rules:

- The job runs with the other automation jobs (`proposals` in `JOBS`). It looks only at open complaints that changed
  since it last looked (`complaints.proposal_checked_at`), at most `PROPOSAL_BATCH` a pass, and leaves complaints
  younger than `PROPOSAL_WAIT_MINUTES` (30) for a later pass, since the consumer may still be sending things.
- One proposal per kind per complaint, ever. A rejected one is not offered again.
- Approving checks the proposal again against the complaint as it is now. If the rules would no longer propose it,
  it is marked `stale` and nothing is done. Otherwise it runs the same route an officer would use by hand, with all
  of that route's permission, scope and state checks.
- Taking a decision is one conditional update, so two officers approving at once never both carry it out.
- Proposals on complaints that closed are marked `stale` on the next pass.
- Reasons shown to the officer are fixed sentences with no consumer data and no figures. Every approval and
  rejection is audited (`proposal.approve`, `proposal.reject`) under the officer's name, on top of the audit rows of
  the action itself.
- Batch approval takes up to 25 at a time; each is checked and carried out on its own, and the ones that cannot go
  are listed with the reason.
