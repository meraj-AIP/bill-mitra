# API contract: accounts, access, complaints and bill review

The backend and the web app both build to this file. Errors are always `{ "detail": string }`, with one exception: a
wrong code on `POST /api/bills/by-usc/verify` answers `{ "detail": { "message": string, "attempts_left": number } }`.
The detailed rules for roles, units, review policy and bill review (decision maths, case states, evidence pack) are in [review-contract.md](review-contract.md). This file lists every route and its shape; it does not repeat those rules.

## Sessions, permissions and scopes

- Access is decided by permissions, never by role names. A role is a named set of permissions from the catalogue in `backend/app/domain/rbac.py`.
- Built-in roles: `admin`, `officer`, `section_ae`, `billing_approver`, `auditor`, `call_centre`, `consumer`. An admin can add custom roles.
- `complaints.create` (log a complaint for a consumer) is held by `call_centre`, `officer` and `section_ae`. `admin`, `auditor` and `billing_approver` do not hold it by default.
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
| `POST /api/auth/login` | `{ login, password }` (login is an email for staff, a 10 digit mobile for consumers) | `Account`, sets the cookie. 401 `Login or password is wrong.` |
| `POST /api/auth/register` | `{ name, mobile, password, consent: true }` mobile `^[6-9]\d{9}$`, password 8+ characters, consent to the privacy notice | `Account` (consumer), signed in. 409 if the mobile is taken, 422 on bad input |
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

Consumers register themselves; staff are created here. Only a `roles.manage` holder can change an account that holds `roles.manage`, `units.manage` or `policy.manage`.

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
| `POST /api/bills` | `self.bills` or `chat.preview` | multipart `file`, `language?` | `BillReport` |
| `GET /api/bills` | `self.bills` or `chat.preview` | `page, page_size, audit_status?, sort=newest or oldest` | `Page<BillRow>`, own bills only |
| `GET /api/bills/{id}` | `self.bills` or `chat.preview`, owner | `language?` | `BillReport`, 404 if not yours |
| `POST /api/bills/{bill_id}/review-request` | `self.bills`, owner | `{ note? (max 500) }`, `language?` | `ReviewSummary`. 409 if a case is already open for the bill |
| `POST /api/bills/{bill_id}/review-request/no-bills` | `self.bills`, owner | `language?` | `ReviewSummary`. Answers the open request for earlier bills with "I do not have them". 409 if no such request is open |
| `POST /api/bills/by-usc/start` | `self.bills` | `{ discom: 'TGSPDCL' or 'TGNPDCL', service_number (5..16 digits) }`, `language?` | 202 `UscStarted`, the same body whether or not the number exists. 503 when the DISCOM lookup or the code sender is not configured, 429 after 5 starts per account or 3 per service number in an hour |
| `POST /api/bills/by-usc/verify` | `self.bills` | `{ discom, service_number, code (6 digits; omit on a development server) }`, `language?` | `BillReport` of the fetched bill (saved as the caller's bill, `source = 'discom'`). 400 `{ detail: { message, attempts_left } }` for a wrong, expired or unknown code (all alike), 429 when locked (5 wrong codes lock for 30 minutes), 404 when no bill comes back, 503 not configured |

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
interface UscStarted { status: 'accepted'; message: string; expires_in_seconds: number;   // 300
  code_required: boolean }   // false only on a development server with OWNERSHIP_CHECK=false
```

Codes are stored hashed and work once. A fetched bill runs through the same capture checks and engine as an upload;
one that fails them is not saved (404). Every start, verify and fetch is audited (`usc.start`, `usc.verify`,
`usc.fetch`) with the masked number only. In development with `OWNERSHIP_CHECK=false` the bill comes from bills already
stored for that number and no code is needed; `APP_ENV=production` refuses to start with that setting.

## Web chat and other signed in routes

- `GET /api/health`, `GET /api/tariffs`, `GET /api/tariffs/calculate`, the WhatsApp webhook: public. Health also returns `whatsapp_number` (from `WHATSAPP_DISPLAY_NUMBER`, or null) so the dashboard can link to the chat.
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
}
// overdue: open and past due_at; rows without due_at fall back to COMPLAINT_REPLY_DAYS.
interface ComplaintMessage {
  id: number; author_kind: 'consumer' | 'officer' | 'system'; author_name: string | null;
  body: string; created_at: string; media_url: string | null;
  delivery: 'sent' | 'failed' | 'stored';   // sent on WhatsApp / could not be sent / shown in the web app
  delivery_note: string | null;             // plain reason when failed, e.g. WhatsApp not connected
}
interface ComplaintDetail extends ComplaintRow {
  bill: { bill_month: string | null; units: number | null; total_payable: number | null;
          bill_amount: number | null; service_masked: string | null; discom: string } | null;
  audit_lines: { code: string; label: string; printed: number | null; expected: number | null;
                 difference: number | null; status: string }[];
  media_url: string | null;   // the bill photo or PDF
  messages: ComplaintMessage[];
  reply_channel: 'whatsapp' | 'web';
  whatsapp_ready: boolean;    // false when the WhatsApp channel is not configured
  description: string | null; // the raiser's own words
  assignee: { id: string; name: string } | null;
  assignable: { id: string; name: string }[];   // in-scope staff with complaints.view, max 50; [] unless the viewer holds complaints.assign
  timeline: { at: string; actor: { kind: 'consumer' | 'system' | 'staff'; name: string | null }; text: string }[];   // oldest first
}
```

| Method and path | Permission | Body / query | Returns |
| --- | --- | --- | --- |
| `GET /api/console/complaints` | `complaints.view` | `page, page_size, status?, discom?, q?` (ticket), `sort=priority, newest or oldest`, `triage?`, `failed?`, `kind?`, `type?`, `priority?`, `source?` (422 for an unknown value) | `Page<ComplaintRow>` in scope. `priority` sort: open, overdue, then urgent types first |
| `POST /api/console/complaints` | `complaints.create` | `{ type, discom, section_id?, service_number? (5..16 digits), contact_mobile? (10 digit Indian mobile), description (3..1000), source: call_centre, office or field, bill_id? }` | 201 `ComplaintDetail`. 403 when the section (or, with no section, the DISCOM queue) is outside the raiser's scope, 422 for a section of another DISCOM. The mobile becomes the WhatsApp reply-to and is never returned. A `bill_id` is linked only when it belongs to that mobile's own WhatsApp account. Audited `complaint.create` with type and source only |
| `POST /api/console/complaints/{ticket}/assign` | `complaints.assign` | `{ account_id }` | `ComplaintDetail`. General complaints only (409 for a reading check, which is assigned from its case, and when closed); 400 when the account is not in `assignable`. Audited `complaint.assign` |
| `GET /api/console/complaints.csv` | `complaints.view` | `status?, discom?, q?, sort=newest or oldest, kind?, type?, priority?, source?` | CSV download, columns ticket, created_at, updated_at, status, discom, bill_month, service_masked, issue, amount, channel, days_open. Audited |
| `GET /api/console/complaints/{ticket}` | `complaints.view` | | `ComplaintDetail`, 404 outside scope |
| `GET /api/console/complaints/{ticket}/options` | `complaints.view` | | `{ triage, options: [{ key, label, text, why, asks }], requests: [{ kind, label, text, why }] }`. Two to four replies chosen by type, status, bill check and thread state (`app/domain/complaint_options.py`); rules only, no model call. Figures only in bill options, from the engine |
| `POST /api/console/complaints/{ticket}/draft` | `complaints.reply` | `{ option_key }` | `{ text, worded_by: 'ai' or 'rules' }`. The option reworded by the model on request; any figure not in the option, any staff word, or no model gives the template. 404 for an option not offered |
| `POST /api/console/complaints/{ticket}/reply` | `complaints.reply` | `{ body (1..1000 chars), status?, asks? }` | `ComplaintDetail`. Sends to the consumer on their channel and records delivery. `asks` (a request kind, from an option) files their next answer under the complaint |
| `POST /api/console/complaints/{ticket}/status` | `complaints.reply` | `{ status }` | `ComplaintDetail`; the consumer gets a short status message |
| `POST /api/console/complaints/{ticket}/request` | `complaints.reply` | `{ kind: meter_photo, bill_photo, details, earlier_bills or payment_proof }` | `ComplaintDetail`; 409 when closed, 422 when the kind does not fit the complaint type |
| `POST /api/console/complaints/{ticket}/messages/{id}/retry` | `complaints.reply` | | `ComplaintDetail`; resends a failed message |
| `POST /api/console/complaints/bulk` | `complaints.reply` | `{ tickets (1..25), status?, send_explanation? }` | `{ done: string[], skipped: { ticket, reason }[] }` |

### The consumer's own complaints (web)

| Method and path | Permission | Body / query | Returns |
| --- | --- | --- | --- |
| `POST /api/complaints` | `self.bills` | `{ type, discom, service_number?, bill_id?, description (3..1000) }`, `language?` | 201 `ConsumerComplaintDetail`. `bill_id` must be the caller's own (404). `wrong_reading` with a bill opens the review case (409 if one is open); without a bill it asks for the bill photo at once |
| `GET /api/complaints` | `self.bills` | `page, page_size (5..50), language?, status?` (one of the neutral codes) | `Page<ConsumerComplaint>`, own only, newest first |
| `GET /api/complaints/{ticket}` | `self.bills` | `language?` | `ConsumerComplaintDetail`, 404 unless it is the caller's |
| `POST /api/complaints/{ticket}/reply` | `self.bills` | `{ body (3..1000) }`, `language?` | `ConsumerComplaintDetail`. 409 unless the complaint is `waiting_for_you` |

```ts
interface ConsumerComplaint { ticket: string; type: TypeCode | null; type_label: string;
  status: 'received' | 'in_progress' | 'waiting_for_you' | 'resolved' | 'closed'; status_label: string;
  created_at: string; updated_at: string; description: string | null;
  service_masked: string | null; bill_month: string | null }
interface ConsumerComplaintDetail extends ConsumerComplaint {
  messages: { from: 'you' | 'bill_mitra'; body: string; at: string }[] }   // staff and system messages show as Bill Mitra
```

No staff name, assignee or role ever appears in the consumer view.

WhatsApp only allows free text within 24 hours of the consumer's last message. Outside that window the reply is sent with the approved template in `WHATSAPP_COMPLAINT_TEMPLATE` when set; otherwise delivery is `failed` with that reason, and the officer sees it.

## Bill review (staff)

Shapes (`CaseRow`, `CaseDetail`, `Decision`, `EvidencePack`, `TimelineEntry`) and decision rules are in [review-contract.md](review-contract.md), sections 5, 6 and 8.

| Method and path | Permission | Body / query | Returns |
| --- | --- | --- | --- |
| `GET /api/review/cases` | `cases.view` | `page, page_size, state?, mine?, overdue?, section_id?, q?` (ticket), `sort=oldest or newest` | `Page<CaseRow>` plus `counts` per state, in scope |
| `GET /api/review/sections` | `cases.view` | | `{ id, name }[]` sections holding cases the caller can see |
| `GET /api/review/cases/{ticket}` | `cases.view` | | `CaseDetail` with `evidence_pack`, `timeline`, `can` and `assignable`. 404 outside scope |
| `POST /api/review/cases/{ticket}/unmask` | `consumer.unmask` | | `{ service_number }`, open case only, audited every time |
| `POST /api/review/cases/{ticket}/assign` | `cases.reassign` | `{ account_id }` | `CaseDetail`; the account must be able to decide in that section |
| `POST /api/review/cases/{ticket}/request` | `cases.request_info` | `{ kind: earlier_bills, meter_photo or note, note? }` | `CaseDetail`; the consumer is messaged on their channel |
| `POST /api/review/cases/{ticket}/preview` | `cases.decide` | `{ corrected_present_reading }` | `{ corrected_units, revised_amount, reduction, needs_approval }` from the engine, nothing saved |
| `POST /api/review/cases/{ticket}/decisions` | `cases.decide` | `{ kind: correct, corrected_reading or custom, corrected_present_reading?, reduction?, reason_code, note (20+ chars), evidence: { kind, id }[] (1..20) }` | `CaseDetail`. 409 when the case is not waiting for a decision |
| `POST /api/review/decisions/{id}/approve` | `cases.approve` | `{ note? }` | `CaseDetail`. 403 on your own decision |
| `POST /api/review/decisions/{id}/reject` | `cases.approve` | `{ note }` | `CaseDetail`. 403 on your own decision (withdraw it instead) |
| `POST /api/review/decisions/{id}/withdraw` | proposer with `cases.decide`, or `cases.approve` | | `CaseDetail`. 409 once applied. The consumer is told if a revision had been announced |
| `POST /api/review/decisions/{id}/applied` | `cases.mark_applied` | `{ billing_ref }` | `CaseDetail`, case Resolved, consumer told. 403 on your own decision |
| `GET /api/review/revisions.csv` | `cases.export` | `from?, to?` (YYYY-MM-DD), `ero_id?` | CSV of revisions in scope. Audited |
