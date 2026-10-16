# Contract: roles, units and AE bill review

Backend and web app build to this file, on top of `docs/api-contract.md`. Errors are `{ "detail": string }`.
Business source: the BRD "Bill Mitra BRD: AE bill review, adjustments and role-based access".

## 1. Permissions, roles, scopes

Access is decided by **permissions**, never by role names in code. A role is a named set of permissions.
Every staff account has exactly one role and one or more **scopes** (units). Consumers have the `consumer` role and no scopes.

Permission catalogue (fixed in code, `app/domain/rbac.py`):

| Permission | Means |
| --- | --- |
| `roles.manage` | Create, edit, delete custom roles |
| `units.manage` | Create and edit units, import units, map unmapped sections |
| `policy.manage` | Edit per-DISCOM review policy (limits, spike thresholds, SLA) |
| `accounts.manage` | Create and edit staff accounts, within own scope; only `roles.manage` holders may grant roles that carry `roles.manage`, `units.manage` or `policy.manage` |
| `console.view` | Department console summary |
| `complaints.view` / `complaints.reply` / `complaints.assign` | General complaint inbox |
| `cases.view` | See wrong-reading cases in scope |
| `cases.request_info` | Ask the consumer for earlier bills, a meter photo or a note |
| `cases.decide` | Record a decision on a case in scope |
| `cases.reassign` | Move a case to another account in scope |
| `cases.approve` | Approve or reject a decision awaiting approval |
| `cases.mark_applied` | Mark an approved revision as applied in the DISCOM billing system |
| `cases.export` | CSV of revisions |
| `consumer.unmask` | See a full service number on an open case in scope (audited every time) |
| `audit.view` | Audit log in scope |
| `chat.preview` | Use the Assistant page as staff |
| `self.bills` | Consumer: own bills, chat, review requests |

Built-in roles (seeded, `builtin = true`, permissions fixed, cannot be deleted):

| Slug | Name | Permissions |
| --- | --- | --- |
| `super_admin` | Super admin | everything EXCEPT `cases.decide`, `cases.approve`, `cases.mark_applied`, `self.bills` (separation of duties: whoever manages roles never moves money) |
| `admin` | Admin | `accounts.manage`, `console.view`, `complaints.view`, `audit.view`, `chat.preview` |
| `officer` | DISCOM officer | `console.view`, `complaints.view`, `complaints.reply`, `complaints.assign`, `cases.view`, `cases.request_info`, `cases.reassign`, `cases.export`, `chat.preview` |
| `section_ae` | Section AE | `console.view`, `complaints.view`, `complaints.reply`, `cases.view`, `cases.request_info`, `cases.decide`, `cases.reassign`, `consumer.unmask` |
| `billing_approver` | Billing approver | `cases.view`, `cases.approve`, `cases.mark_applied`, `cases.export`, `consumer.unmask` |
| `auditor` | Auditor | `console.view`, `complaints.view`, `cases.view`, `cases.export`, `audit.view` |
| `consumer` | Consumer | `self.bills` |

Custom roles: created by `roles.manage` holders from the catalogue. A custom role may hold any permission except that
`roles.manage` can only be combined with `units.manage`, `policy.manage`, `accounts.manage`, `audit.view`, `console.view`
(no money permissions alongside role management). Hard rules enforced in code whatever the role: nobody approves or
marks applied their own decision; a decision needs a reason code, a note of 20+ characters and at least one evidence item.

Migration of existing accounts: `admin` accounts become `super_admin` (owner decision: both current admins), `officer` stays
`officer` with its DISCOM as scope, `consumer` stays `consumer`.

## 2. Units (hierarchy)

`kind` is one of `discom`, `circle`, `division`, `subdivision`, `section`, `ero`. Tree by `parent_id`:
discom > circle > division > subdivision > section. An `ero` sits under a division; a section may point at one ERO
(`ero_id`). The two DISCOM units (TGSPDCL, TGNPDCL) are seeded at startup.

A scope on unit U covers U and every unit under it. An ERO scope covers the sections whose `ero_id` is that ERO.
A section matches a bill when the bill's DISCOM matches and the normalised printed `Sec:` name (upper case, letters and
digits only) equals the section's normalised name or one of its `aliases`. Unmatched printed names are recorded as
**unmapped sections** (name, DISCOM, count, last seen) for a `units.manage` holder to map.

```ts
interface Unit { id: string; kind: 'discom'|'circle'|'division'|'subdivision'|'section'|'ero'; name: string;
  code: string | null; discom: 'TGSPDCL'|'TGNPDCL'; parent_id: string | null; ero_id: string | null;
  aliases: string[]; active: boolean; children_count: number }
interface Scope { unit_id: string; name: string; kind: Unit['kind'] }
interface Role { slug: string; name: string; description: string; permissions: string[]; builtin: boolean; accounts: number }
```

`Account` (from `/api/auth/me` and admin lists) gains: `role` (slug, any role), `role_name`, `permissions: string[]`,
`scopes: Scope[]`. `discom` stays for compatibility (the DISCOM of the first scope, or null).

## 3. Review policy (per DISCOM)

```ts
interface Policy { discom: 'TGSPDCL'|'TGNPDCL';
  ae_limit: number | null;          // Rs an AE may reduce alone on a corrected reading; null = no limit (default)
  custom_needs_approval: boolean;   // default false (owner decision: AE decides everything)
  spike_ratio: number;              // default 2.0: units above 2x the household median
  spike_min_increase: number;       // default 500: and at least Rs 500 more than the median month would cost
  min_history_months: number;       // default 3
  decision_sla_days: number }       // default 3 (working days not modelled; calendar days)
```

## 4. Wrong-reading detection

After a bill is checked (chat and dashboard), `app/domain/review.py` compares its units with the median of the
household's previous months (printed table plus own uploads, at most 6). Flagged when history has at least
`min_history_months` months AND units > `spike_ratio` x median AND engine amount at these units minus engine amount at
the median >= `spike_min_increase`; or when the present reading is lower than the previous reading. Pure rules, no model.

```ts
interface Spike { flagged: boolean; reason: 'above_normal'|'reading_went_back'|null; units: number;
  median_units: number | null; months_used: number; ratio: number | null; usual_amount: number | null }
```
The bill report (`GET/POST /api/bills...`) gains `analysis.spike: Spike` and `review: ReviewSummary | null`.
In chat, a flagged bill gets one extra message with a button "Ask AE to check" (reply id `review_request`).

## 5. Cases

A case is a complaint of `kind: 'wrong_reading'` (general complaints keep `kind: 'general'`), routed to the section of
its bill. Routing: section unit by match above; assignee = an active account with `cases.decide` scoped to exactly that
section, the one with the fewest open cases; none = unassigned at the section's division (officers there see it).
The thread, info requests and WhatsApp delivery reuse the existing complaint machinery.

Review states (derived, in this order): `awaiting_review` (no decision, no open request), `info_requested` (an open
info request), `awaiting_approval`, `decided` (latest decision approved, no reduction or reduction recorded),
`applied` (latest revision marked applied), `rejected` (latest decision rejected; back to the AE).

```ts
type ReviewState = 'awaiting_review'|'info_requested'|'awaiting_approval'|'decided'|'applied'|'rejected';
interface CaseRow { ticket: string; created_at: string; state: ReviewState; overdue: boolean; days_open: number;
  section: string | null; discom: string; bill_month: string | null; service_masked: string | null;
  units: number | null; median_units: number | null; printed_amount: number | null; usual_amount: number | null;
  assignee: { id: string; name: string } | null; channel: 'whatsapp'|'web' }
interface Decision { id: number; kind: 'correct'|'corrected_reading'|'custom'; status: 'approved'|'pending_approval'|'rejected'|'withdrawn';
  original_amount: number; revised_amount: number; reduction: number;
  corrected_present_reading: number | null; corrected_units: number | null;
  reason_code: ReasonCode; note: string; evidence: Evidence[];
  proposed_by: { id: string; name: string }; proposed_at: string;
  decided_by: { id: string; name: string } | null; decided_at: string | null; decision_note: string | null;
  applied_at: string | null; billing_ref: string | null; revision: number | null }
type ReasonCode = 'photo_misread'|'wrong_meter'|'estimated_reading'|'meter_faulty'|'category_wrong'|'bill_correct'|'other';
interface Evidence { kind: 'message'|'bill'|'note'; id: string; label: string }
interface CaseDetail extends CaseRow {
  bill: BillReport['bill'];  // masked, as on the dashboard
  media_url: string | null; mime_type: string | null;
  audit_lines: AuditLine[]; spike: Spike;
  history: { month: string; units: number; amount: number; source: 'printed'|'uploaded'|'this_bill' }[];
  messages: ComplaintMessage[];         // the thread, as in api-contract
  requests: { id: number; kind: 'earlier_bills'|'meter_photo'|'note'; note: string | null; status: 'open'|'answered'; created_at: string }[];
  decisions: Decision[];                // newest first
  policy: Policy;
  can: { decide: boolean; approve: boolean; mark_applied: boolean; request_info: boolean; reassign: boolean; unmask: boolean };
  assignable: { id: string; name: string }[] }   // for reassign, in scope
interface ReviewSummary { ticket: string; state: ReviewState;
  revision: { original_amount: number; revised_amount: number; reason: string /* consumer language */;
              decided_by: string; decided_at: string; status: 'pending_update'|'applied' } | null }
```

## 6. Endpoints

| Method and path | Permission | Body / query | Returns |
| --- | --- | --- | --- |
| `GET /api/admin/permissions` | `roles.manage` | | `{ code, label, group }[]` |
| `GET /api/admin/roles` | `accounts.manage` | | `Role[]` |
| `POST /api/admin/roles` | `roles.manage` | `{ name, description, permissions }` | `Role` (slug derived from name) |
| `PATCH /api/admin/roles/{slug}` | `roles.manage` | `{ name?, description?, permissions? }` | `Role`; 400 for built-in permissions |
| `DELETE /api/admin/roles/{slug}` | `roles.manage` | | 204; 409 if accounts hold it or built-in |
| `GET /api/admin/units` | `units.manage` or `accounts.manage` | `parent_id?` (omit = DISCOMs), `q?`, `kind?` | `Unit[]` |
| `POST /api/admin/units` | `units.manage` | `{ kind, name, code?, parent_id, ero_id?, aliases? }` | `Unit`; 400 for a kind that does not fit under the parent |
| `PATCH /api/admin/units/{id}` | `units.manage` | `{ name?, code?, ero_id?, aliases?, active? }` | `Unit` |
| `POST /api/admin/units/import` | `units.manage` | CSV file: `kind,name,code,parent_code,discom,ero_code,aliases` (aliases `;` separated) | `{ created, updated, errors: { line, detail }[] }` |
| `GET /api/admin/units/unmapped` | `units.manage` | | `{ name, discom, count, last_seen }[]` |
| `POST /api/admin/units/unmapped/map` | `units.manage` | `{ name, discom, section_id }` | 204 (name added as alias; open cases re-routed) |
| `GET /api/admin/policy` | `policy.manage` | | `Policy[]` |
| `PUT /api/admin/policy/{discom}` | `policy.manage` | `Policy` fields | `Policy` |
| `POST/PATCH /api/admin/accounts...` | `accounts.manage` | now `role` (any slug except `consumer`) and `scopes: string[]` (unit ids) | `Account`; a scope outside the actor's own scope is refused |
| `GET /api/review/cases` | `cases.view` | `page, page_size, state?, mine?(bool), overdue?(bool), section_id?, q?(ticket), sort=oldest\|newest` | `Page<CaseRow>`, scoped |
| `GET /api/review/cases/{ticket}` | `cases.view` | | `CaseDetail`; 404 out of scope |
| `POST /api/review/cases/{ticket}/unmask` | `consumer.unmask` | | `{ service_number }`, audited |
| `POST /api/review/cases/{ticket}/assign` | `cases.reassign` | `{ account_id }` | `CaseDetail` |
| `POST /api/review/cases/{ticket}/request` | `cases.request_info` | `{ kind, note? }` | `CaseDetail`; the consumer is messaged |
| `POST /api/review/cases/{ticket}/preview` | `cases.decide` | `{ corrected_present_reading }` | `{ corrected_units, revised_amount, reduction, needs_approval }` (engine, nothing saved) |
| `POST /api/review/cases/{ticket}/decisions` | `cases.decide` | `{ kind, corrected_present_reading?, reduction?, reason_code, note, evidence: {kind,id}[] }` | `CaseDetail` |
| `POST /api/review/decisions/{id}/approve` | `cases.approve` | `{ note? }` | `CaseDetail`; 403 own decision |
| `POST /api/review/decisions/{id}/reject` | `cases.approve` | `{ note }` | `CaseDetail` |
| `POST /api/review/decisions/{id}/withdraw` | proposer or `cases.approve` | | `CaseDetail`; 409 once applied |
| `POST /api/review/decisions/{id}/applied` | `cases.mark_applied` | `{ billing_ref }` | `CaseDetail`; 403 own decision |
| `GET /api/review/revisions.csv` | `cases.export` | `from?, to?, ero_id?` | CSV |
| `POST /api/bills/{bill_id}/review-request` | `self.bills`, bill owner | `{ note? }` | `ReviewSummary`; 409 if a case is already open for the bill |

Decision rules: `correct` = no change (reduction 0, approved at once). `corrected_reading` = engine reprices the bill
month at units = corrected present reading minus previous reading, tariff in force, same load, period and Gruha Jyothi
as the bill; reduction = printed bill amount minus repriced amount (must be > 0 and <= printed amount). Needs approval
when policy `ae_limit` is set and reduction > it. `custom` = the AE types `reduction` (> 0, <= printed amount); needs
approval when `custom_needs_approval`. An approved reduction creates the next revision number for that bill and
notifies the consumer in their language on their channel. The original bill is never edited.

## 7. Audit actions (new)

`role.create`, `role.update`, `role.delete`, `unit.create`, `unit.update`, `unit.import`, `unit.map`, `policy.update`,
`case.route`, `case.assign`, `case.request`, `case.unmask`, `decision.create`, `decision.approve`, `decision.reject`,
`decision.withdraw`, `decision.applied`, `revision.export`. Details never contain a full service number or phone.
