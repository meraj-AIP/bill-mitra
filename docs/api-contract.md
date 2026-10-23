# API contract: accounts, access, complaints and bill review

The backend and the web app both build to this file. Every error has the one shape in [Errors](#errors) below.
The detailed rules for roles, units, review policy and bill review (decision maths, case states, evidence pack) are in [review-contract.md](review-contract.md). This file lists every route and its shape; it does not repeat those rules.

## Errors

Every 4xx and 5xx answer, from any route or middleware, is this envelope ([errors-contract.md](errors-contract.md)):

```ts
interface ApiErrorBody { detail: {
  code: string;      // stable snake_case key, e.g. not_found, invalid, rate_limited, code_wrong, server_error
  message: string;   // safe to show as is; in the request's language where the route takes `language`
  ref: string;       // short request id, also in the X-Request-Id header and the server log line
  [extra: string]: unknown;   // per route, e.g. attempts_left on a wrong USC code, max_mb on a file too large
} }
```

- Every response, error or not, carries `X-Request-Id`. Support finds the log line by it.
- 500: `{ code: "server_error", message: "Something went wrong on our side. Reference A1B2C3.", ref: "A1B2C3" }`. The
  log has the exception type, the code lines and the ref, never the error text or the request body.
- 422: one readable sentence. A validator's own words when it wrote some (`"A service number is 5 to 16 digits."`),
  otherwise "Some details are missing or not in the right form. Please check them and try again." No field paths.
- 429: says what was limited, for example `{ code: "rate_limited", message: "Too many uploads. Please wait a minute.",
  limit: "bill-upload" }`.
- No Python error text reaches a client. Domain refusals written for people (`Refusal` in `app/core/errors.py`) are
  passed through; anything else becomes "That could not be done. Please check the details and try again."
- Translated (`language` query, form field or body): the bill dashboard, bill by USC, the consumer's complaints, the
  web chat upload and `POST /api/auth/otp/start`. A 422 or 500 uses the `language` query parameter when there is one.

```json
{ "detail": { "code": "code_wrong", "message": "That code is not right or has expired. You have 4 tries left, or you can ask for a new code.", "ref": "7F3A0C", "attempts_left": 4 } }
{ "detail": { "code": "bill_not_found", "message": "बिल नहीं मिला।", "ref": "0B91D2" } }
```

## Sessions, permissions and scopes

- Access is decided by permissions, never by role names. A role is a named set of permissions from the catalogue in `backend/app/domain/rbac.py`.
- Built-in roles: `admin`, `officer`, `section_ae`, `billing_approver`, `auditor`, `call_centre`, `consumer`. An admin can add custom roles.
- `complaints.create` (log a complaint for a consumer) is held by `call_centre`, `officer` and `section_ae`. `admin`, `auditor` and `billing_approver` do not hold it by default.
- `complaints.assign` (hand a complaint over) is held by `admin`, `officer`, `call_centre` and `section_ae`. Existing databases grant it to `call_centre` and `section_ae` once, when the hand-off columns first appear.
- Every staff account has one role and one or more scopes (unit ids). A scope covers that unit and everything below it. Consumers have the `consumer` role and no scopes.
- Every staff route runs `require_perm(...)` and then a scope check. Something outside the caller's scope is a 404, not a 403, so its existence does not leak.
- Permissions are read from the role on every request, so a role change applies at once.
- The session is an httpOnly cookie, `bm_session` by default (`SESSION_COOKIE`), SameSite=Lax, Secure when `COOKIE_SECURE=true`, valid for `SESSION_HOURS` (12). The web app never reads it; it sends requests with credentials and reacts to 401 by going to `/login`.
- 401 means not signed in. 403 means signed in but without the permission.
- A consumer's bills and conversation belong to the account (`acct:<id>`), so history follows them across devices.
- Five wrong passwords lock a login for 15 minutes. Login errors never say which part was wrong.

```ts
interface Scope { unit_id: string; name: string; kind: 'discom'|'circle'|'division'|'subdivision'|'section'|'ero' }
interface Account {
  id: string; role: string;            // any role slug
  role_name: string; permissions: string[]; scopes: Scope[];
  login: string; name: string;
  discom: 'TGSPDCL' | 'TGNPDCL' | null;   // kept for older clients: the one DISCOM all scopes sit in, else null
  active: boolean; last_login_at: string | null; created_at: string;   // "YYYY-MM-DD HH:MM:SS" UTC
  consent_version: string | null;   // privacy notice version a consumer agreed to
}
interface Page<T> { items: T[]; total: number; page: number; page_size: number }
```

## Auth (public unless noted)

| Method and path | Body | Returns |
| --- | --- | --- |
| `POST /api/auth/login` | `{ login, password }` (staff, by work email) | `Account`, sets the cookie. 401 `Login or password is wrong.` |
| `GET /api/auth/otp/channels` | none | `{ channels: ("sms" or "whatsapp")[], on_screen, whatsapp_number }`. `on_screen` is development only: no channel is connected and the code is shown on the page |
| `POST /api/auth/otp/start` | `{ mobile, purpose: "signup" or "login", channel, discom? }`. Sign up needs `discom`: the mobile must be registered with it for at least one connection | `{ channel, expires_in, resend_in, connections, dev_code }`. 404 not registered with that DISCOM, 429 too many codes or locked, 503 channel or DISCOM lookup not available, 502 not sent. A development server with no channel shows the code on screen only for the sample consumer, `DEMO_OTP_MOBILE` and numbers with no account; any other number gets 403 |
| `POST /api/auth/otp/signup` | `{ mobile, code, name, discom, consent: true }` | `Account` (consumer), signed in, with the DISCOM's connections for the mobile kept masked. A mobile that already has an account is signed in to it. 400 wrong or expired code, 429 locked after 5 wrong codes (30 minutes) |
| `POST /api/auth/otp/login` | `{ mobile, code }` | `Account`, signed in. 400 wrong code, 404 no account for the mobile, 403 switched off |
| `GET /api/auth/connections` (signed in) | none | The connections found for the consumer's mobile at sign up: `{ discom, service_masked, section }[]` |
| `POST /api/auth/logout` | none | 204, clears the cookie |
| `GET /api/auth/me` | none | `Account` or 401 |
| `POST /api/auth/password` (signed in) | `{ current_password, new_password }` | 204, ends the account's other sessions. 400 if current is wrong |

## Privacy

| Method and path | Who | Returns |
| --- | --- | --- |
| `GET /api/privacy` | public | `{ version, retention_days, contact: string or null, purposes: string[] }` |
| `DELETE /api/me` | consumer | 204, erases bills, chat and unshared photos, unlinks complaints (kept as the department record), anonymises the account and signs out. Staff get 403; an administrator closes staff accounts |

STOP in the chat and `POST /api/web/reset` also delete unshared photos. A sweep at startup removes data older than `RETENTION_DAYS` (180) unless a complaint needs it.

## Staff accounts, audit and health

| Method and path | Permission | Body / query | Returns |
| --- | --- | --- | --- |
| `GET /api/admin/accounts` | `accounts.manage` | `page, page_size (5..50), role?, active? (true/false), q?` (login or name) | `Page<Account>` newest first, only accounts within the caller's scope |
| `POST /api/admin/accounts` | `accounts.manage` | `{ role (any slug except consumer), login (email), name, scopes: string[] (1..50 unit ids), password }`. Older clients may send `discom` instead of `scopes` | `Account`. 409 if the login exists. 403 for a scope outside the caller's own, or for a role carrying `roles.manage`, `units.manage` or `policy.manage` when the caller lacks `roles.manage` |
| `PATCH /api/admin/accounts/{id}` | `accounts.manage` | any of `{ name, role, scopes, active }` | `Account`. 400 when you deactivate, demote or rescope yourself, or give a consumer a staff role. Role, scope or active changes end that account's sessions |
| `POST /api/admin/accounts/{id}/reset-password` | `accounts.manage` | `{ password }` | 204, ends that account's sessions |
| `GET /api/admin/audit` | `audit.view` | `page, page_size, action?` | `Page<{ id, ts, actor_id, actor_name, action, target, detail }>` newest first, limited to entries in the caller's scope |
| `GET /api/admin/health` | `accounts.manage` | | provider modes plus today's warning counts |
| `GET /api/admin/operations` | `audit.view` or `accounts.manage` | `page, page_size (5..100), kind? (inbound, outbound or extract), sort=newest or oldest` | `ParkedPage`: failures the queues gave up on. A scoped account sees only outbound rows of complaints in its scope; rows without a ticket need a global account |
| `POST /api/admin/operations/{kind}/{id}/retry` | `audit.view` or `accounts.manage` | | 204, back in its queue and due now. 404 when not parked or not in scope, 409 when it has no number left to send to (a one-time code, a WhatsApp bill read). Audited `operations.retry` |
| `POST /api/admin/operations/{kind}/{id}/dismiss` | `audit.view` or `accounts.manage` | | 204; the number and message it held are dropped. 404 when not parked or not in scope. Audited `operations.dismiss` |

Consumers register themselves; staff are created here. Only a `roles.manage` holder can change an account that holds `roles.manage`, `units.manage` or `policy.manage`.

```ts
// Ids are per queue, hence kind in every path. Never a message body or a number.
interface ParkedPage { items: Parked[]; total: number; page: number; page_size: number }
interface Parked { id: string; kind: 'inbound' | 'outbound' | 'extract'; ticket: string | null; attempts: number;
  last_error: string | null;   // exception class and HTTP status only, e.g. "HTTPStatusError 503"
  created_at: string; failed_at: string | null }
```

A parked inbound turn raises the alert `inbound_failed` (perm `audit.view`, no message text). An outbound complaint
message that fails after queuing raises `delivery_failed` for the complaint's holder, or for its unit with perm
`complaints.reply` when nobody holds it. See docs/reliability-contract.md and docs/reliability-audit.md.

## Roles

```ts
interface Role { slug: string; name: string; description: string; permissions: string[]; builtin: boolean;
  accounts: number;       // accounts holding it
  customised: boolean;    // a built-in role whose permissions differ from its default
  locked: boolean }       // permissions cannot change (the consumer role)
```

| Method and path | Permission | Body | Returns |
| --- | --- | --- | --- |
| `GET /api/admin/permissions` | `roles.manage` | | `{ code, label, group }[]` |
| `GET /api/admin/roles` | `accounts.manage` | | `Role[]`, built-in first |
| `POST /api/admin/roles` | `roles.manage` | `{ name, description?, permissions }` | `Role`, slug made from the name. 409 if it exists, 400 for an unknown permission, an empty list or a clash |
| `PATCH /api/admin/roles/{slug}` | `roles.manage` | `{ name?, description?, permissions? }` | `Role`. Works on custom and built-in roles. 400 for the consumer role, for admin without `roles.manage`, or for `roles.manage` together with `cases.decide`, `cases.approve`, `cases.mark_applied` or `self.bills` |
| `POST /api/admin/roles/{slug}/reset` | `roles.manage` | | `Role` back to its shipped name, description and permissions. 404 for a custom role |
| `DELETE /api/admin/roles/{slug}` | `roles.manage` | | 204. 409 for a built-in role or one an account still holds |

Every role write is audited (`role.create`, `role.update`, `role.reset`, `role.delete`).

## Units

```ts
interface Unit { id: string; kind: Scope['kind']; name: string; code: string | null; discom: 'TGSPDCL' | 'TGNPDCL';
  parent_id: string | null; ero_id: string | null; aliases: string[]; active: boolean; children_count: number }
```

| Method and path | Permission | Body / query | Returns |
| --- | --- | --- | --- |
| `GET /api/admin/units` | `units.manage`, `accounts.manage` or `complaints.create` | `parent_id?` (omit for the DISCOMs), `q?`, `kind?` | `Unit[]` in scope |
| `POST /api/admin/units` | `units.manage` | `{ kind, name, code?, parent_id, ero_id?, aliases? (max 20) }` | `Unit`. 400 when the kind does not fit under the parent, 409 on a clash, 404 for a parent outside scope |
| `PATCH /api/admin/units/{id}` | `units.manage` | any of `{ name, code, ero_id, aliases, active }` | `Unit` |
| `POST /api/admin/units/import` | `units.manage` | multipart CSV, header `kind,name,code,parent_code,discom,ero_code,aliases` (aliases `;` separated), under 1 MB, at most 5000 rows | `{ created, updated, errors: { line, detail }[] }`. Rows for a DISCOM outside scope are errors |
| `GET /api/admin/units/unmapped` | `units.manage` | | `{ name, discom, count, last_seen }[]` |
| `POST /api/admin/units/unmapped/map` | `units.manage` | `{ name, discom, section_id }` | 204. The name becomes an alias and open cases that carried it are re-routed |

## Review policy

```ts
interface Policy { discom: 'TGSPDCL' | 'TGNPDCL'; ae_limit: number | null; custom_needs_approval: boolean;
  spike_ratio: number; spike_min_increase: number; min_history_months: number; decision_sla_days: number }
// defaults: null, false, 2.0, 500, 3, 3. With these the AE decides alone.
```

| Method and path | Permission | Body | Returns |
| --- | --- | --- | --- |
| `GET /api/admin/policy` | `policy.manage` | | `Policy[]` in scope |
| `PUT /api/admin/policy/{discom}` | `policy.manage` | any `Policy` fields; left out keeps the current value, an explicit `ae_limit: null` means no limit | `Policy`. 403 outside scope |

## Bills (consumer)

| Method and path | Permission | Body / query | Returns |
| --- | --- | --- | --- |
| `POST /api/bills` | `self.bills` or `chat.preview` | multipart `file`, `language?` | `BillReport`; or 202 `ReadJob` when the reader is down for now (provider down, timeout, rate limit). The photo is kept and read again after 1, 5 and 15 minutes |
| `GET /api/bills/jobs/{job_id}` | `self.bills` or `chat.preview`, owner | | `ReadJob`, 404 if not yours. When `done` with a `bill_id`, the bill is in `GET /api/bills` and `GET /api/bills/{id}` |
| `GET /api/bills` | `self.bills` or `chat.preview` | `page, page_size, audit_status?, sort=newest or oldest` | `Page<BillRow>`, own bills only |
| `GET /api/bills/{id}` | `self.bills` or `chat.preview`, owner | `language?` | `BillReport`, 404 if not yours |
| `POST /api/bills/{bill_id}/review-request` | `self.bills`, owner | `{ note? (max 500) }`, `language?` | `ReviewSummary`. 409 if a case is already open for the bill |
| `POST /api/bills/{bill_id}/review-request/no-bills` | `self.bills`, owner | `language?` | `ReviewSummary`. Answers the open request for earlier bills with "I do not have them". 409 if no such request is open |
| `POST /api/bills/by-usc/start` | `self.bills` | `{ discom: 'TGSPDCL' or 'TGNPDCL', service_number (5..16 digits) }`, `language?` | 202 `UscStarted`, the same body whether or not the number exists. 503 when the DISCOM lookup or the code sender is not configured, 429 after 5 starts per account or 3 per service number in an hour |
| `POST /api/bills/by-usc/verify` | `self.bills` | `{ discom, service_number, code (6 digits; omit on a development server) }`, `language?` | `BillReport` of the fetched bill (saved as the caller's bill, `source = 'discom'`). 400 `code_wrong` with `attempts_left` for a wrong, expired or unknown code (all alike but the ref), 429 when locked (5 wrong codes lock for 30 minutes), 404 when no bill comes back, 503 not configured |

```ts
interface BillRow { id: string; created_at: string; bill_month: string | null; discom: string | null; units: number | null;
  total_payable: number | null;            // final total: revised amount plus printed arrears once revised
  original_total_payable: number | null;   // as printed
  revised_amount: number | null; under_review: boolean;
  audit_status: string | null; overcharge: number; service_masked: string | null }
// BillReport gains:
//   review: ReviewSummary | null
//   final: { bill_amount: number; total_payable: number | null; revised: boolean; status: 'pending_update' | 'applied' | null } | null
interface ReviewSummary { ticket: string;
  state: 'received' | 'waiting_for_you' | 'revised' | 'no_change';
  requested_months: string[]; received_months: string[];   // YYYY-MM
  revision: { original_amount: number; revised_amount: number; original_total: number | null; revised_total: number | null;
              reason: string; office: string; decided_at: string; status: 'pending_update' | 'applied' } | null }
```

The consumer side never names who reviews. `office` is the DISCOM.

```ts
interface ReadJob { job_id: string; status: 'queued' | 'running' | 'done' | 'failed';
  bill_id: string | null;   // set when done and the bill was saved
  outcome: 'checked' | 'retake' | 'not_a_bill' | 'reading_failed' | 'reading_off' | null;   // null until finished
  problem: string | null;   // the problem key below, when finished without a bill
  detail: string | null }   // in the uploader's language: while waiting, or why there is no bill and what to do
// BillReport gains problem: string | null, and outcome_reason is in the request's language.
// problem keys: chk_readings, chk_energy_units, chk_net_units, chk_export_readings, chk_charges_sum, chk_total,
//   unread_units, unread_energy, unread_bill_amount, unread_low_confidence, poor_quality, meter_unreadable, meter,
//   not_a_bill, other_discom (never priced), file_unopenable, file_too_long, read_failed, reading_off
// CaptureReport gains problem_code ('no_units' | 'unreadable' | 'check' | 'low_confidence' | null) and problem_key;
// each check gains values: { [name]: number }, the printed figures and the rules' result.
```

A finished read always ends: `done` with a `bill_id`, `done` with `outcome` retake or not_a_bill and a reason, or
`failed` with `outcome: 'reading_failed'`. The page never has to keep polling a finished job.

```ts
interface UscStarted { status: 'accepted'; message: string; expires_in_seconds: number;   // 300
  code_required: boolean }   // false only on a development server with OWNERSHIP_CHECK=false
```

Codes are stored hashed and work once. A fetched bill runs through the same capture checks and engine as an upload;
one that fails them is not saved (404). Every start, verify and fetch is audited (`usc.start`, `usc.verify`,
`usc.fetch`) with the masked number only. In development with `OWNERSHIP_CHECK=false` the bill comes from bills already
stored for that number and no code is needed; `APP_ENV=production` refuses to start with that setting.

## Web chat and other signed in routes

- `GET /api/health`, `GET /api/tariffs`, `GET /api/tariffs/calculate`, the WhatsApp webhook: public. Health also returns `whatsapp_number` (from `WHATSAPP_DISPLAY_NUMBER`, or null) so the dashboard can link to the chat, and `queues: { inbox: { queued, failed }, outbox: { queued, failed }, extract: { queued, failed }, oldest_queued_s: number | null }` (counts only).
- `POST /api/web/upload`, `POST /api/web/messages`, `POST /api/web/reset`: `self.bills` or `chat.preview`. `reset` takes no body.
- `GET /api/web/history?before=<id>&limit=<1..100>`: same permission. The saved conversation, newest page first and items oldest first: `{ items: [{ id, at, sender: 'user' or 'bot', body }], has_more }`. A user body is `{ kind, text?, reply_id?, media_id?, mime_type?, transcript? }`; a bot body is the WhatsApp-shaped message. Every channel's turns are saved; STOP, `POST /api/web/reset`, account deletion and the retention sweep erase them. The WhatsApp number is never part of a saved message.
- `GET /api/media/{id}`: any signed in account (an `<img>` sends the cookie).
- `GET /api/console/summary`: `console.view`. Query `days` (1..365, default 30) and `discom`; staff whose scopes sit in one DISCOM always see that DISCOM. Returns `days`, `discom`, `reads { total, trusted_first_time, reread_rescued, retake, not_a_bill, failed, median_ms, p90_ms }`, `explanations { llm_pass, llm_fallback, template }`, `complaints_by_status`, `complaints_overdue` and the window counts.

## Complaints (general and the inbox)

Statuses: `Open`, `In progress`, `Resolved`, `Rejected`. Tickets look like `BM-261016-7KQ2D` (date plus 5 random characters). General complaints are raised in the chat (WhatsApp or the web Assistant), on the consumer web page, or by staff for a caller; replies go to the consumer's channel. Wrong bill cases are complaints with `kind: 'wrong_reading'` and are worked in the review queue below. Types are in [complaints-contract.md](complaints-contract.md) section 1.

```ts
type TypeCode = 'high_bill' | 'wrong_reading' | 'estimated_bill' | 'wrong_category' | 'payment_not_updated'
  | 'arrears_dispute' | 'bill_not_received' | 'meter_issue' | 'meter_burnt' | 'power_outage'
  | 'voltage_fluctuation' | 'supply_other';
type Priority = 'urgent' | 'high' | 'normal' | 'low';
type Source = 'consumer_web' | 'consumer_chat' | 'whatsapp' | 'call_centre' | 'office' | 'field';
interface ComplaintType { code: TypeCode; category: 'billing' | 'meter' | 'supply'; category_label: string;
  label: string; label_key: string; needs_bill: boolean; priority: Priority;
  target_days: number | null;   // null for wrong_reading: the DISCOM's review SLA applies
  route: 'section' | 'division' | 'review' }
```

`GET /api/complaint-types?language=te|en|hi|ur` (public, default `en`) returns `ComplaintType[]` in catalogue order,
labels in that language.

```ts
type ComplaintStatus = 'Open' | 'In progress' | 'Resolved' | 'Rejected';
interface ComplaintRow {
  ticket: string; created_at: string; updated_at: string | null; status: ComplaintStatus;
  service_masked: string | null; bill_month: string | null; discom: string | null;
  issue: string; amount: number | null; language: string | null;
  channel: 'whatsapp' | 'web' | null;   // where the consumer raised it, so where replies go
  kind: 'general' | 'wrong_reading'; triage: 'overcharge' | 'bill_correct' | 'needs_check';
  delivery_failed: boolean; days_open: number; overdue: boolean;   // open longer than COMPLAINT_REPLY_DAYS
  messages_count: number; last_message_at: string | null;
  type: TypeCode | null; type_label: string | null;   // English label for staff
  priority: Priority | null; due_at: string | null;   // UTC "YYYY-MM-DD HH:MM:SS"
  source: Source | null;
  raised_by: string | null;    // staff name when staff logged it, null when the consumer raised it
  ownership: 'verified' | 'unverified' | 'not_needed' | null;
  demo: boolean;               // development demo row
  section: string | null;      // matched section name, null in a DISCOM or division queue
  waiting_on: 'staff' | 'consumer' | 'none';   // consumer: a request or the chat waits for their answer; none: closed
  assignee_name: string | null;   // who holds it
}
// overdue: open and past due_at; rows without due_at fall back to COMPLAINT_REPLY_DAYS.
interface ComplaintMessage {
  id: number; author_kind: 'consumer' | 'officer' | 'system'; author_name: string | null;
  body: string; created_at: string;
  media_url: string | null;    // /api/console/complaints/{ticket}/media/{id}: staff in scope only
  media_type: string | null;   // e.g. image/jpeg, application/pdf
  delivery: 'sent' | 'queued' | 'failed' | 'stored';   // sent on WhatsApp / WhatsApp did not answer, retried for up to
                                                       // 24 hours / could not be sent / shown in the web app
  delivery_note: string | null;             // plain reason when queued or failed, e.g. WhatsApp not connected
}
interface ComplaintDetail extends ComplaintRow {
  bill: { bill_month: string | null; units: number | null; total_payable: number | null;
          bill_amount: number | null; service_masked: string | null; discom: string } | null;
  audit_lines: { code: string; label: string; printed: number | null; expected: number | null;
                 difference: number | null; status: string }[];
  media_url: string | null;   // the bill photo or PDF, on the same scoped media route
  messages: ComplaintMessage[];
  reply_channel: 'whatsapp' | 'web';
  whatsapp_ready: boolean;    // false when the WhatsApp channel is not configured
  description: string | null; // the raiser's own words
  assignee: { id: string; name: string } | null;   // who it is "with"
  handoff: { by: { id: string; name: string } | null;   // null when it was routed to the section AE automatically
             note: string | null; at: string | null } | null;   // null while nobody holds it
  assignable: { id: string; name: string }[];   // whom this viewer may hand it to now (rules below); [] otherwise
  can_return: boolean;          // the viewer holds it and may send it back to whoever handed it over
  requests: ComplaintRequest[]; // newest first
  timeline: { at: string; actor: { kind: 'consumer' | 'system' | 'staff'; name: string | null }; text: string }[];   // oldest first
}
```

```ts
interface ComplaintRequest {   // the same shape on review cases
  id: number; kind: 'meter_photo' | 'bill_photo' | 'details' | 'earlier_bills' | 'payment_proof' | 'note';
  note: string | null; status: 'open' | 'answered'; created_at: string; answered_at: string | null;
  answer: { message_id: number; media_url: string | null; media_type: string | null;
            body: string | null;   // null for a photo sent without words
            at: string } | null;   // null while open, or when it lapsed with no reply
}
interface ComplaintAssist {
  summary: string;                          // 2 to 3 English lines for staff
  missing: string[];                        // what we still do not know, max 4
  questions: { text: string; why: string }[];   // max 3, text in the consumer's language, send as a "note" request
  next_action: { kind: 'reply_option' | 'request' | 'status' | 'assign'; key: string; why: string;
                 account_id: string | null } | null;   // assign only: the section's AE when the viewer may hand to them
  worded_by: 'ai' | 'rules';
}
```

`next_action.key` is always on offer right now: a reply option key or a request kind from `/options`, a status other
than the current one (`In progress`, `Resolved`, `Rejected`, open complaints only) or `hand_over` (only when the
viewer has someone to hand to). Anything else the model picks is replaced by the rules' pick (the first reply option).
Every model line holding a number the facts do not hold is dropped, as is a question naming staff; a summary that fails
gives the whole rules answer. Without a model the rules give the same shape.

Hand-off rules (permissions, never role names): a holder of `accounts.manage` (admin) may hand to anyone in scope who
can see complaints; a holder of `cases.decide` (the section AE) to another decider or back to desk staff
(`complaints.assign`); other desk staff (officer, call centre) to a decider. Nobody hands to themselves or to the
current holder. A complaint raised in a section goes to that section's AE (an active account scoped on exactly that
section that can see complaints and decide cases, the least busy first); unplaced ones wait in the DISCOM queue.
Routing, each hand-off and each send back write the timeline (`Routed to <name>`, `Handed to <name>: <note>`, `Sent back
to <name>: <note>`) and raise `complaint_assigned` for the new holder. A consumer message raises `consumer_replied` for
the holder (or, unheld, for its unit with `complaints.reply`), once until staff write again. A consumer message never
reaches a closed complaint.

| Method and path | Permission | Body / query | Returns |
| --- | --- | --- | --- |
| `GET /api/console/complaints` | `complaints.view` | `page, page_size, status?, discom?, q?` (ticket), `sort=priority, newest or oldest`, `triage?`, `failed?`, `kind?`, `type?`, `priority?`, `source?`, `with_me?` (held by the caller), `waiting_on_me?` (held by the caller and `waiting_on` staff) (422 for an unknown value) | `Page<ComplaintRow>` in scope. `priority` sort: open, overdue, then urgent types first |
| `POST /api/console/complaints` | `complaints.create` | `{ type, discom, section_id?, service_number? (5..16 digits), contact_mobile? (10 digit Indian mobile), description (3..1000), source: call_centre, office or field, bill_id? }` | 201 `ComplaintDetail`. 403 when the section (or, with no section, the DISCOM queue) is outside the raiser's scope, 422 for a section of another DISCOM. The mobile becomes the WhatsApp reply-to and is never returned. A `bill_id` is linked only when it belongs to that mobile's own WhatsApp account. Audited `complaint.create` with type and source only |
| `POST /api/console/complaints/{ticket}/assign` | `complaints.assign` | `{ account_id, note (10..300) }` | `ComplaintDetail`. General complaints only (409 for a reading check, which is moved from its case, when closed, or when it changed hands meanwhile); 400 when the account is not in `assignable`; 422 without a note. Audited `complaint.handoff` with the name and note |
| `POST /api/console/complaints/{ticket}/return` | `complaints.reply` | `{ note (10..300) }` | `ComplaintDetail`. Back to whoever handed it over. 409 unless the caller holds a handed over complaint, or when that person can no longer see it. Audited `complaint.return` |
| `POST /api/console/complaints/{ticket}/assist` | `complaints.reply` | | `ComplaintAssist`, on a button press only. Audited `assist.complaint` with `worded by ai or rules`, no text |
| `GET /api/console/complaints/{ticket}/media/{media_id}` | `complaints.view` (or `cases.view` on a reading check) | | The file, for a photo or bill on this complaint (a message, its bill, a bill attached to the case). 404 outside scope or for any other file |
| `GET /api/console/complaints.csv` | `complaints.view` | `status?, discom?, q?, sort=newest or oldest, kind?, type?, priority?, source?` | CSV download, columns ticket, created_at, updated_at, status, discom, bill_month, service_masked, issue, amount, channel, days_open. Audited |
| `GET /api/console/complaints/{ticket}` | `complaints.view` | | `ComplaintDetail`, 404 outside scope |
| `GET /api/console/complaints/{ticket}/options` | `complaints.view` | | `{ triage, options: [{ key, label, text, why, asks }], requests: [{ kind, label, text, why }] }`. Two to four replies chosen by type, status, bill check and thread state (`app/domain/complaint_options.py`); rules only, no model call. Figures only in bill options, from the engine |
| `POST /api/console/complaints/{ticket}/draft` | `complaints.reply` | `{ option_key }` | `{ text, worded_by: 'ai' or 'rules' }`. The option reworded by the model on request; any figure not in the option, any staff word, or no model gives the template. 404 for an option not offered |
| `POST /api/console/complaints/{ticket}/reply` | `complaints.reply` | `{ body (1..1000 chars), status?, asks? }` | `ComplaintDetail`. Sends to the consumer on their channel and records delivery. `asks` (a request kind, from an option) files their next answer under the complaint |
| `POST /api/console/complaints/{ticket}/status` | `complaints.reply` | `{ status }` | `ComplaintDetail`; the consumer gets a short status message |
| `POST /api/console/complaints/{ticket}/request` | `complaints.reply` | `{ kind: meter_photo, bill_photo, details, earlier_bills, payment_proof or note, note? (3..300, required for note and only for note) }` | `ComplaintDetail`; 409 when closed, 422 when the kind does not fit the complaint type or the note names staff. A note request sends the question under the details line |
| `POST /api/console/complaints/{ticket}/messages/{id}/retry` | `complaints.reply` | | `ComplaintDetail`; resends a failed message |
| `POST /api/console/complaints/bulk` | `complaints.reply` | `{ tickets (1..25), status?, send_explanation? }` | `{ done: string[], skipped: { ticket, reason }[] }` |

### The consumer's own complaints (web)

| Method and path | Permission | Body / query | Returns |
| --- | --- | --- | --- |
| `POST /api/complaints` | `self.bills` | `{ type, discom, service_number?, bill_id?, description (3..1000) }`, `language?` | 201 `ConsumerComplaintDetail`. `bill_id` must be the caller's own (404). `wrong_reading` with a bill opens the review case (409 if one is open); without a bill it asks for the bill photo at once |
| `GET /api/complaints` | `self.bills` | `page, page_size (5..50), language?, status?` (one of the neutral codes) | `Page<ConsumerComplaint>`, own only, newest first |
| `GET /api/complaints/{ticket}` | `self.bills` | `language?` | `ConsumerComplaintDetail`, 404 unless it is the caller's |
| `POST /api/complaints/{ticket}/reply` | `self.bills` | `{ body (3..1000) }`, `language?` | `ConsumerComplaintDetail`. 409 unless the complaint is `waiting_for_you`. Answers every open request |
| `POST /api/complaints/{ticket}/photo` | `self.bills` | multipart `file` (JPG, PNG, WEBP, HEIC or PDF, under `MAX_UPLOAD_MB`, type read from the bytes), `caption?` (form, up to 1000), `language?` | `ConsumerComplaintDetail`. 409 unless `waiting_for_you`, 413 too large, 415 wrong type. Stored as their message, answers every open request |
| `GET /api/complaints/{ticket}/media/{media_id}` | `self.bills` | | The file, only for a photo the caller sent on their own complaint; 404 otherwise |

```ts
interface ConsumerComplaint { ticket: string; type: TypeCode | null; type_label: string;
  status: 'received' | 'in_progress' | 'waiting_for_you' | 'resolved' | 'closed'; status_label: string;
  created_at: string; updated_at: string; description: string | null;
  service_masked: string | null; bill_month: string | null }
interface ConsumerComplaintDetail extends ConsumerComplaint {
  messages: { from: 'you' | 'bill_mitra'; body: string; at: string;   // staff and system messages show as Bill Mitra
              media_url: string | null; media_type: string | null }[] }   // only on their own photos
```

No staff name, assignee or role ever appears in the consumer view.

WhatsApp only allows free text within 24 hours of the consumer's last message. Outside that window the reply is sent with the approved template in `WHATSAPP_COMPLAINT_TEMPLATE` when set; otherwise delivery is `failed` with that reason, and the officer sees it.

Every message to a consumer goes through the outbox. When WhatsApp does not answer after three quick tries, delivery
is `queued` and the message is retried after 1, 5, 15 and 60 minutes, then every 3 hours, for up to 24 hours; the
thread updates to `sent` or `failed` as it changes. A queued message cannot be sent again from the thread (only a
`failed` one can), so the consumer never gets two copies.

## Bill review (staff)

Shapes (`CaseRow`, `CaseDetail`, `Decision`, `EvidencePack`, `TimelineEntry`) and decision rules are in [review-contract.md](review-contract.md), sections 5, 6 and 8.

```ts
interface CaseAssist {
  summary: string;
  conflicts: string[];   // always the rules': spike, misread signal, estimated reading, charges above tariff
  questions: { text: string; why: string }[];   // send as a request of kind "note"
  suggested: 'draft' | 'ask_consumer' | 'decide';   // "draft" only when the rules have a drafted decision
  why: string;           // one English line on why that step; a model line with an unknown figure gives the rules' line
  worded_by: 'ai' | 'rules';
}
```

Every alert item carries `href`: `/review/{ticket}` for a case, `/console/complaints/{ticket}` for any other complaint,
null when the alert has no ticket (a digest, a section pattern).

Alerts on cases: `case_assigned` to the decider a case is routed or reassigned to, `consumer_replied` to its holder
(or, unheld, its unit with `cases.decide`) once per staff turn, `decision_returned` to the proposer when an approver
rejects their decision.

| Method and path | Permission | Body / query | Returns |
| --- | --- | --- | --- |
| `GET /api/review/cases` | `cases.view` | `page, page_size, state?, mine?, overdue?, section_id?, q?` (ticket), `sort=oldest or newest` | `Page<CaseRow>` plus `counts` per state, in scope |
| `GET /api/review/sections` | `cases.view` | | `{ id, name }[]` sections holding cases the caller can see |
| `GET /api/review/cases/{ticket}` | `cases.view` | | `CaseDetail` with `evidence_pack`, `timeline`, `can` and `assignable`. 404 outside scope. `messages` carry `media_url` and `media_type`, `requests` are `ComplaintRequest` (with `answer`), attached bills carry `media_type`; every file is on the scoped complaint media route |
| `POST /api/review/cases/{ticket}/assist` | `cases.view` | | `CaseAssist`, on a button press only. 409 when the bill was erased. Audited `assist.case`, no text |
| `POST /api/review/cases/{ticket}/unmask` | `consumer.unmask` | | `{ service_number }`, open case only, audited every time |
| `POST /api/review/cases/{ticket}/assign` | `cases.reassign` | `{ account_id }` | `CaseDetail`; the account must be able to decide in that section. Raises `case_assigned` for them |
| `POST /api/review/cases/{ticket}/request` | `cases.request_info` | `{ kind: earlier_bills, meter_photo or note, note? }` | `CaseDetail`; the consumer is messaged on their channel |
| `POST /api/review/cases/{ticket}/preview` | `cases.decide` | `{ corrected_present_reading }` | `{ corrected_units, revised_amount, reduction, needs_approval }` from the engine, nothing saved |
| `POST /api/review/cases/{ticket}/decisions` | `cases.decide` | `{ kind: correct, corrected_reading or custom, corrected_present_reading?, reduction?, reason_code, note (20+ chars), evidence: { kind, id }[] (1..20) }` | `CaseDetail`. 409 when the case is not waiting for a decision |
| `POST /api/review/decisions/{id}/approve` | `cases.approve` | `{ note? }` | `CaseDetail`. 403 on your own decision |
| `POST /api/review/decisions/{id}/reject` | `cases.approve` | `{ note }` | `CaseDetail`. 403 on your own decision (withdraw it instead). Raises `decision_returned` for the proposer |
| `POST /api/review/decisions/{id}/withdraw` | proposer with `cases.decide`, or `cases.approve` | | `CaseDetail`. 409 once applied. The consumer is told if a revision had been announced |
| `POST /api/review/decisions/{id}/applied` | `cases.mark_applied` | `{ billing_ref }` | `CaseDetail`, case Resolved, consumer told. 403 on your own decision |
| `GET /api/review/revisions.csv` | `cases.export` | `from?, to?` (YYYY-MM-DD), `ero_id?` | CSV of revisions in scope. Audited |
