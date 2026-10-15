# API contract: accounts, admin, complaints

The backend and the web app both build to this file. Errors are always `{ "detail": string }`.

## Sessions and roles

- Roles: `admin` (manages accounts, sees everything), `officer` (department staff: console and complaints, optionally limited to one DISCOM), `consumer` (their own bills, chat and complaints).
- The session is an httpOnly cookie `bm_session` (SameSite=Lax, Secure when `COOKIE_SECURE=true`), valid for `SESSION_HOURS` (12). The web app never reads it; it sends requests with credentials and reacts to 401 by going to `/login`.
- 401 means not signed in. 403 means signed in but the role cannot do this.
- A consumer's bills and conversation belong to the account (`acct:<id>`), so history follows them across devices.
- Five wrong passwords lock a login for 15 minutes. Login errors never say which part was wrong.

```ts
type Role = 'admin' | 'officer' | 'consumer';
interface Account {
  id: string; role: Role; login: string; name: string;
  discom: 'TGSPDCL' | 'TGNPDCL' | null;   // officers only; null means all DISCOMs
  active: boolean; last_login_at: string | null; created_at: string;   // "YYYY-MM-DD HH:MM:SS" UTC
  consent_version: string | null;   // privacy notice version a consumer agreed to
}
interface Page<T> { items: T[]; total: number; page: number; page_size: number }
```

## Auth (public unless noted)

| Method and path | Body | Returns |
| --- | --- | --- |
| `POST /api/auth/login` | `{ login, password }` (login is an email for staff, a 10 digit mobile for consumers) | `Account`, sets the cookie. 401 `Login or password is wrong.` |
| `POST /api/auth/register` | `{ name, mobile, password, consent: true }` mobile `^[6-9]\d{9}$`, password 10+ characters, consent to the privacy notice | `Account` (consumer), signed in. 409 if the mobile is taken, 422 on bad input |
| `POST /api/auth/logout` | none | 204, clears the cookie |
| `GET /api/auth/me` | none | `Account` or 401 |
| `POST /api/auth/password` (signed in) | `{ current_password, new_password }` | 204, ends the account's other sessions. 400 if current is wrong |

## Privacy

| Method and path | Who | Returns |
| --- | --- | --- |
| `GET /api/privacy` | public | `{ version, retention_days, contact: string or null, purposes: string[] }` |
| `DELETE /api/me` | consumer | 204, erases bills, chat and unshared photos, unlinks complaints (kept as the department record), anonymises the account and signs out. Staff get 403 |

STOP in the chat and `POST /api/web/reset` also delete unshared photos. A sweep at startup removes data older than `RETENTION_DAYS` (180) unless a complaint needs it.

## Admin (role admin)

| Method and path | Body / query | Returns |
| --- | --- | --- |
| `GET /api/admin/accounts` | `page, page_size (5..50), role?, active? (true/false), q?` (matches login or name) | `Page<Account>` newest first |
| `POST /api/admin/accounts` | `{ role: 'admin' or 'officer', login (email), name, discom (null or DISCOM), password }` | `Account`. 409 if the login exists |
| `PATCH /api/admin/accounts/{id}` | any of `{ name, role, discom, active }` | `Account`. 400 when an admin tries to deactivate or demote themselves. Deactivating ends that account's sessions |
| `POST /api/admin/accounts/{id}/reset-password` | `{ password }` | 204, ends that account's sessions |
| `GET /api/admin/audit` | `page, page_size, action?` | `Page<{ id, ts, actor_id, actor_name, action, target, detail }>` newest first |

Consumers register themselves; admins create staff. Admins can deactivate any account.

## Existing routes, now signed in

- `GET /api/health`, `GET /api/tariffs`, `GET /api/tariffs/calculate`, the WhatsApp webhook: public as before.
- `POST /api/bills`, `GET /api/bills`, `GET /api/bills/{id}`: any signed-in account; the owner is the account. The `X-Session-Id` header is gone.
- `POST /api/web/upload`, `POST /api/web/messages`, `POST /api/web/reset`: any signed-in account. `session_id` is no longer sent; `reset` takes no body.
- `GET /api/web/history?before=<id>&limit=<1..100>`: any signed-in account. The saved conversation, newest page first and items oldest first: `{ items: [{ id, at, sender: 'user' or 'bot', body }], has_more }`. A user body is `{ kind, text?, reply_id?, media_id?, mime_type?, transcript? }`; a bot body is the WhatsApp-shaped message. Every channel's turns are saved; STOP, `POST /api/web/reset`, account deletion and the retention sweep erase them. The WhatsApp number is never part of a saved message.
- `GET /api/media/{id}`: any signed-in account (an `<img>` sends the cookie).
- `GET /api/console/summary`: admin or officer. Query `days` (1..365, default 30) and `discom`; an officer with a DISCOM is always scoped to it. Adds `days`, `discom`, `reads { total, trusted_first_time, reread_rescued, retake, not_a_bill, failed, median_ms, p90_ms }`, `explanations { llm_pass, llm_fallback, template }`, `complaints_by_status`, `complaints_overdue` (Open or In progress older than 7 days). `complaints` and `overcharge_flagged` now cover the window only.

## Complaints

Statuses: `Open`, `In progress`, `Resolved`, `Rejected`. Tickets look like `BM-261016-7KQ2D` (date plus 5 random characters).

```ts
type ComplaintStatus = 'Open' | 'In progress' | 'Resolved' | 'Rejected';
interface ComplaintRow {
  ticket: string; created_at: string; updated_at: string | null; status: ComplaintStatus;
  service_masked: string | null; bill_month: string | null; discom: string | null;
  issue: string; amount: number | null; language: string | null;
  channel: 'whatsapp' | 'web' | null;   // where the consumer raised it, so where replies go
  messages_count: number; last_message_at: string | null;
}
interface ComplaintMessage {
  id: number; author_kind: 'consumer' | 'officer' | 'system'; author_name: string | null;
  body: string; created_at: string;
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
  reply_channel: 'whatsapp' | 'web';   // where an officer reply will go
  whatsapp_ready: boolean;             // false when the WhatsApp channel is not configured
}
```

| Method and path | Who | Body / query | Returns |
| --- | --- | --- | --- |
| `GET /api/console/complaints` | admin, officer | `page, page_size, status?, discom?, q?` (ticket), `sort=newest or oldest` | `Page<ComplaintRow>`. An officer with a DISCOM sees only that DISCOM |
| `GET /api/console/complaints.csv` | admin, officer | same filters as the list | CSV download, at most 5000 rows, columns ticket, created_at, updated_at, status, discom, bill_month, service_masked, issue, amount, channel, days_open |
| `GET /api/console/complaints/{ticket}` | admin, officer | | `ComplaintDetail`, 404 outside the officer's DISCOM |
| `POST /api/console/complaints/{ticket}/reply` | admin, officer | `{ body (1..1000 chars), status? }` | `ComplaintDetail`. Sends to the consumer on their channel and records delivery |
| `POST /api/console/complaints/{ticket}/status` | admin, officer | `{ status }` | `ComplaintDetail`; the consumer gets a short status message |
| `GET /api/me/complaints` | signed in | `page, page_size` | `Page<ComplaintRow>` (own only) |
| `GET /api/me/complaints/{ticket}` | signed in | | `ComplaintDetail` (own only, 404 otherwise) |
| `POST /api/me/complaints/{ticket}/reply` | signed in | `{ body }` | `ComplaintDetail` |
| `POST /api/bills/{bill_id}/complaint` | signed in, bill owner | `{ note? (max 500) }` | `ComplaintDetail` for the new complaint. 409 if one is already open for that bill |

WhatsApp only allows free text within 24 hours of the consumer's last message. Outside that window the reply is sent with the approved template in `WHATSAPP_COMPLAINT_TEMPLATE` when set; otherwise delivery is `failed` with that reason, and the officer sees it.
