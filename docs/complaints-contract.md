# Complaints contract: types, who raises them, bills by USC, ownership

Builds on the existing complaints (`store/complaints.py`, `api/complaints.py`, the console inbox) and the review
cases. Hard rules still hold: the engine produces every number, consumers never learn who handles their complaint,
no consumer data in logs, every action audited.

## 1. Complaint types (catalogue in code, `app/domain/complaint_types.py`)

| Category | Type code | Label | Needs a bill | Priority | Target days | Goes to |
| --- | --- | --- | --- | --- | --- | --- |
Owner's scope (17 Oct 2026): the grievance groups TGSPDCL and TGNPDCL use, with billing in the most detail. Nothing
else for now (no safety, connection, staff conduct or "other" types).

| Category | Type code | Label | Needs a bill | Priority | Target days | Goes to |
| --- | --- | --- | --- | --- | --- | --- |
| Billing | `high_bill` | Bill is too high | no | normal | 7 | section |
| Billing | `wrong_reading` | Meter reading on the bill is wrong | yes (or fetched) | normal | policy SLA | the AE review case flow |
| Billing | `estimated_bill` | Bill was estimated, meter not read | no | normal | 7 | section |
| Billing | `wrong_category` | Wrong tariff category or load | no | normal | 15 | section |
| Billing | `payment_not_updated` | Payment made but not shown | no | high | 3 | section |
| Billing | `arrears_dispute` | Arrears or old dues are wrong | no | normal | 7 | section |
| Billing | `bill_not_received` | Did not get this month's bill | no | low | 7 | section |
| Meter | `meter_issue` | Meter not working properly | no | high | 3 | section |
| Meter | `meter_burnt` | Meter is burnt | no | urgent | 1 | section |
| Supply | `power_outage` | No power at my home | no | urgent | 1 | section |
| Supply | `voltage_fluctuation` | Low or fluctuating voltage | no | high | 3 | section |
| Supply | `supply_other` | Other supply problem (frequent cuts, one phase) | no | normal | 7 | section |

Each type: `code, category, label (en), label_key (lang pack key for te/en/hi/ur), needs_bill, priority
(urgent|high|normal|low), target_days (null for wrong_reading: the review policy applies), route
(section|division|review)`. `GET /api/complaint-types` (public, no auth) returns the list with labels in
`?language=`. Chat shows the three categories as buttons (Billing, Meter, Supply), then that category's types as a list.

Placement: by the section printed on the bill, or the section the DISCOM records give for the USC, or the section a
staff member picks. Unknown: the DISCOM queue, recorded as unmapped like today. `wrong_reading` with a bill opens the existing review case; without a bill, a general complaint of
type `wrong_reading` is created and the consumer is asked for the bill photo (existing info request).

## 2. Data model (additive migration on `complaints`)

`type TEXT` (catalogue code, existing rows `other` unless kind wrong_reading -> `wrong_reading`), `priority TEXT`,
`due_at TEXT`, `source TEXT` (`consumer_web | consumer_chat | whatsapp | call_centre | office | field`),
`raised_by TEXT` (account id for staff raised, null for consumers), `service_number_hash TEXT` (sha256 with a server
pepper, for matching; the plain number is never stored, `service_masked` keeps the last 4), `contact_hash TEXT`,
`description TEXT` (consumer or staff words, max 1000), `ownership TEXT` (`verified | unverified | not_needed`),
`demo INTEGER NOT NULL DEFAULT 0`.

## 3. Who raises complaints

New permission `complaints.create`: "Log a complaint for a consumer (phone, walk-in) or from the field".

| Role | complaints.create | Why |
| --- | --- | --- |
| consumer | own only, through `self.bills` | the main way in |
| call_centre (new built-in) | yes | 1912 agents log calls; perms `console.view, complaints.view, complaints.create, complaints.reply` |
| officer | yes | walk-ins at the office |
| section_ae | yes | field findings in their section |
| billing_approver | no | approves money, does not originate cases |
| admin | no | manages access; must not be able to fabricate records it oversees (an admin can still grant it by editing a role) |
| auditor | no | independence |

Staff raise: `POST /api/console/complaints` (perm `complaints.create`), body `{type, discom, section_id | null,
service_number | null, contact_mobile | null, description, source: "call_centre" | "office" | "field",
bill_id | null}`. The section must be in the raiser's scope. `contact_mobile` (Indian mobile, 10 digits) becomes the
complaint's reply-to so updates reach the consumer on WhatsApp; stored like today's reply_to, never logged. Response:
the `ComplaintDetail`. Audit `complaint.create` with type and source only. A staff member never sees bills for a USC
through this route.

Consumer raise (web): `POST /api/complaints` (perm `self.bills`), body `{type, discom, service_number | null,
bill_id | null, description}`. `GET /api/complaints` (own, paged, newest first) and `GET /api/complaints/{ticket}`
(own only, 404 otherwise) return the consumer view: `{ticket, type, type_label, status_label (neutral: received,
in_progress, waiting_for_you, resolved, closed), created_at, updated_at, description, service_masked, bill_month,
messages: [{from: "you" | "bill_mitra", body, at}]}`. Staff names never appear; staff messages show as "Bill Mitra".
Consumers can reply to a complaint that asks them something (`POST /api/complaints/{ticket}/reply`).

Chat (WhatsApp and web chat): "Raise a complaint" works without a bill: category list, then type list, then DISCOM
(two buttons), then USC (typed, optional with a "Skip" button), then a one-line description, then preview and send.
With a checked bill in the conversation, the bill's facts fill DISCOM, USC and section. Lang keys for every prompt and
type label in te, en, hi, ur; Telugu as people speak.

## 4. Bill by USC (`app/services/discom_bills.py`)

Connector `fetch_bill(discom, service_number) -> FetchedBill | None` and `registered_mobile_hash(discom,
service_number) -> str | None`, driven by `DISCOM_BILLS_URL` and `DISCOM_BILLS_TOKEN` (10 s timeout, service number
never logged). Not configured in production: the flow says it is not available yet and asks for a photo.

Development mode: `APP_ENV=development` (default) with `OWNERSHIP_CHECK=false` serves bills already stored in this
database for that service number (newest first) instead of calling the DISCOM, and skips the ownership check. In
`APP_ENV=production` the server refuses to start with `OWNERSHIP_CHECK=false`. No request can change either.

Fetched bill: run through the same checks and engine as an upload, saved as the consumer's bill with
`source = "discom"` (new column on bills), report shown like an upload.

Ownership:
- WhatsApp: the sender's verified number hash is compared with the registered mobile hash. Match: fetch. No match:
  neutral "We could not confirm this connection is yours. Please send a photo of your bill instead."
- Web and web chat: `POST /api/bills/by-usc/start {discom, service_number}` always answers 202 with the same body
  whether or not the USC exists; when a registered mobile exists a 6 digit code is sent to it through
  `notify.send_code` (WhatsApp template or SMS provider; none configured: the flow is unavailable).
  `POST /api/bills/by-usc/verify {discom, service_number, code}` returns the BillReport. Codes are stored hashed,
  valid 5 minutes, 5 attempts, then locked 30 minutes. Rate limits: per account 5 starts an hour, per USC 3 an hour.
- Every start, verify and fetch audited (`usc.start`, `usc.verify`, `usc.fetch`) with the masked number only.

## 5. Demo complaints (development only)

`python -m app.tools.demo_complaints seed | remove`. Refuses when `APP_ENV=production`. About 24 complaints across
the types, spread over the last 30 days, in both DISCOMs, using real section names and structure seen on uploaded
bills (Isnapur and Kondapur sections, Sangareddy ERO, category 1B(i) DOMESTIC, realistic units and amounts priced by
the engine). Service numbers are fake (`99` prefix, masked as usual), contact numbers `9999999xxx`, no names. Mostly billing types, a few meter and supply. Mixed
statuses, sources and messages, a few overdue, two escalated, one power outage. Rows carry `demo = 1`; the console
shows a "Demo" chip; `remove` deletes only demo rows and their messages. The startup mock purge must not delete them.

## 6. Frontend

- Consumer web: a Complaints page (nav item for consumers): "Raise a complaint" (type picker grouped by category with
  plain labels, DISCOM, USC optional, pick one of my bills optional, description), my complaints list (paged) and a
  complaint detail (status steps, what we have, the conversation, reply box when we asked something). Neutral copy.
  "Get my bill with my USC" on the dashboard: DISCOM + USC, then the code step, then the report.
- Staff: "New complaint" in the inbox for `complaints.create` holders (source, type, DISCOM, section picker in scope,
  USC optional, caller mobile optional, description). Inbox gains type, priority and source columns and filters (in
  the URL), due and overdue chips, Demo chip.
- Complaint detail (staff), redesigned: header (ticket, type, priority, status, due), the consumer facts (masked
  USC, DISCOM, section, bill month, source, raised by, ownership), the linked bill summary when there is one, the
  timeline (who did what, System for automatic steps), the conversation, and actions (reply, status, assign, request
  info) in one side column.
