export interface JourneyStep {
  title: string;
  body: string;
  edges: string[];
  payload: string;
  planned?: boolean;
}

export interface Journey {
  name: string;
  /** Shows how staff work a case. Consumers never learn who checks their bill, so they do not see these. */
  staffOnly?: boolean;
  steps: JourneyStep[];
}

export const JOURNEYS: Journey[] = [
  {
    name: 'A consumer sends a bill',
    steps: [
      { title: 'Photo sent on WhatsApp', body: 'The consumer sends the bill to the Bill Mitra number, the way they send any photo.',
        edges: ['consumer>meta'], payload: '{ "type": "image",\n  "image": { "id": "<WhatsApp media id>", "mime_type": "image/jpeg" } }' },
      { title: 'Meta calls our webhook', body: 'The signature is checked, a retried message is dropped, and the phone number becomes a one way pseudonym. The turn is handed on so Meta gets its answer fast.',
        edges: ['meta>ingress', 'ingress>queue'], payload: 'POST /api/whatsapp/webhook\nX-Hub-Signature-256 checked, message id seen once\nuser_id = "wa:" + sha256(number); number kept only on a complaint' },
      { title: 'A worker picks it up', body: 'The photo is downloaded through the Graph API and saved under its own hash.',
        edges: ['queue>svc', 'svc>media'], payload: 'Inbound(channel="whatsapp", kind="image", media_id="<sha256 prefix>.jpg")' },
      { title: 'The bill is read', body: 'A quick first look decides whether it is a bill at all. Then a careful read fills a fixed list of fields; a tall slip is read in overlapping crops.',
        edges: ['svc>prov'], payload: 'classify -> electricity_bill | meter | other_bill | other\nExtractedBill(units, readings, dates, line_items, bill_amount, total_payable, ...)' },
      { title: 'Checked before it is trusted', body: 'Readings, charges, totals and billing days must add up. If they do not, the bill is read once more; if it still fails, the consumer is asked for a retake.',
        edges: ['svc>engine'], payload: 'present - previous == units\nsum(charges) == bill_amount\nbill_amount + arrears == total_due\nbilling days == days between readings' },
      { title: 'Every line checked', body: 'The engine picks the tariff in force for the bill month and checks each printed charge within one rupee.',
        edges: ['tgerc>engine', 'svc>engine'], payload: 'version_for(bill_month) -> TGERC order in force\naudit -> verified | mismatch | partial | not_checkable' },
      { title: 'Worded, then guarded', body: 'The text model gets only the facts. Any figure not in the facts and the checked template goes out instead.',
        edges: ['svc>prov', 'svc>guard'], payload: 'guard.check(text, facts)\npassed -> model text\nfailed -> template from composer.py' },
      { title: 'Voice note made', body: 'Sarvam speaks the reply in Telugu, cached by hash and converted so it shows as a voice note.',
        edges: ['svc>prov', 'svc>media'], payload: 'tts(lang="te") -> OGG Opus chunks' },
      { title: 'Reply goes out', body: 'The voice note, then a summary card with up to three buttons.',
        edges: ['svc>sender', 'sender>meta', 'meta>consumer'], payload: '{ "type": "interactive", "interactive": { "type": "button",\n  "action": { "buttons": [ max 3, titles up to 20 characters ] } } }' },
      { title: 'It reaches the staff side', body: 'A bill_read event is stored with its section, and the officer\'s console counts move.',
        edges: ['svc>db', 'svc>obs'], payload: 'events += { type: "bill_read", section, audit_status, units, amount }' },
    ],
  },
  {
    name: 'An officer resolves a complaint',
    staffOnly: true,
    steps: [
      { title: 'Consumer taps Raise complaint', body: 'The complaint is built from the checked bill, so it carries the engine figures.',
        edges: ['consumer>meta', 'meta>ingress', 'ingress>queue', 'queue>svc'], payload: 'button_reply id="complain" -> intent complain' },
      { title: 'Ticket opened', body: 'Stored in Bill Mitra with its DISCOM. With 1912 access it is registered there too.',
        edges: ['svc>db', 'svc>crm'], payload: 'complaints += { ticket, discom, issue, amount, status: "Open" }' },
      { title: 'Alert reaches the officer', body: 'The scheduler watches tickets close to their SLA and tells the right officer.', planned: true,
        edges: ['sched>cat', 'cat>db', 'sched>desk'], payload: 'alert sla_risk(scope) -> tickets due within 24 hours' },
      { title: 'Officer signs in', body: 'Sign in gives the role and the unit. Every query after that is limited to that unit and the units below it.',
        edges: ['officer>sso', 'sso>staffapi', 'staffapi>rbac'], payload: 'require_perm("complaints.view")\nin_scope(account.unit_id, complaint.unit) -> else 404' },
      { title: 'Officer asks the assistant', body: 'It runs catalogue metrics inside the officer\'s scope and the guard checks its answer.', planned: true,
        edges: ['officer>desk', 'desk>staffapi', 'staffapi>agent', 'agent>cat', 'agent>prov', 'agent>guard'], payload: 'run_metric("bill_check", bill) -> printed vs engine, line by line\nguard: every figure traced' },
      { title: 'Officer replies and resolves', body: 'The reply and the status change are written with the officer\'s name in the audit log.',
        edges: ['desk>staffapi', 'staffapi>actions', 'actions>db'], payload: 'POST /api/console/complaints/{ticket}/reply\nPOST /api/console/complaints/{ticket}/status' },
      { title: '1912 updated', body: 'Status syncs back so the call centre sees the same thing.', planned: true,
        edges: ['actions>crm'], payload: 'PATCH 1912/tickets/{ticket} { status: "Resolved" }' },
      { title: 'Consumer told on WhatsApp', body: 'Inside 24 hours the reply goes as text. Past that, the approved template goes out instead, and a failed send is shown to the officer.',
        edges: ['actions>queue', 'queue>sender', 'sender>meta', 'meta>consumer'], payload: 'text "Update on your complaint {ticket}: ..."\nelse template WHATSAPP_COMPLAINT_TEMPLATE, params: [ticket, status]' },
    ],
  },
  {
    name: 'A wrong bill is reviewed',
    staffOnly: true,
    steps: [
      { title: 'Consumer taps Bill looks wrong', body: 'The button sits on every bill card. The consumer is never told who checks it, only that it is being checked.',
        edges: ['consumer>meta', 'meta>ingress', 'ingress>queue', 'queue>svc'], payload: 'button_reply id="report_bill" -> intent dispute' },
      { title: 'Spike checked, case opened', body: 'The units are compared with the consumer\'s own earlier months. The case opens either way; a spike is flagged for the AE.',
        edges: ['svc>review', 'review>engine'], payload: 'spike = units vs average of earlier months\ncomplaints += { kind: "wrong_reading", bill_id, spike }' },
      { title: 'Routed to the section AE', body: 'The section printed on the bill is matched to a unit by name or alias. A name nobody has mapped waits for an admin to map it.',
        edges: ['review>db'], payload: '"Sec: ISNAPUR" -> units(kind="section", alias match)\ncase.section_id, assigned to that section\'s AE' },
      { title: 'Evidence pack built', body: 'Everything the AE needs, gathered before they open the case. When the DISCOM records are connected, earlier months come from there too.',
        edges: ['review>engine', 'review>billing', 'review>db'], payload: 'evidence_pack: this_bill, printed_history, uploads,\n  discom_records, spike, requested_bills' },
      { title: 'Missing bills asked for', body: 'If fewer than three earlier months are on file, the consumer is asked for those bills straight away. Uploads that match are added to the case.',
        edges: ['review>sender', 'sender>meta', 'meta>consumer'], payload: 'request(kind="previous_bills", months=[...up to 3])\nconsumer sees: "Please send your last bills" (no name, no role)' },
      { title: 'AE opens the case', body: 'The AE sees only cases in their section. The pack, the bill, the readings and the timeline are on one page.',
        edges: ['officer>desk', 'desk>staffapi', 'staffapi>rbac', 'staffapi>review'], payload: 'GET /api/review/cases/{id}\nrequire_perm("cases.view") and in_scope(section_id)' },
      { title: 'AE records a decision', body: 'Bill correct, a corrected reading, or a custom reduction. The engine prices a corrected reading; surcharge and arrears stay as printed.',
        edges: ['staffapi>actions', 'review>engine'], payload: 'corrected_reading: reduction = price(printed units) - price(corrected units)\nreason, note of 20+ characters and evidence required' },
      { title: 'Second approval if policy asks', body: 'Off by default: the AE decides. A DISCOM can set an AE limit or ask for approval on custom reductions. Nobody approves their own.',
        edges: ['staffapi>rbac', 'actions>db'], payload: 'policy: { ae_limit: null, custom_needs_approval: false }\napprover != decider' },
      { title: 'Revised amount is final', body: 'The consumer\'s bill now shows the revised amount as what they owe, with the original kept beside it.',
        edges: ['review>db', 'review>sender', 'sender>meta', 'meta>consumer'], payload: 'GET /api/bills -> total_payable = final\noriginal_total_payable kept' },
      { title: 'Who did what, on the timeline', body: 'Every step is written with who did it: the consumer, the system or a named staff member. The audit log holds the same.',
        edges: ['actions>db'], payload: 'timeline: [{ at, actor: consumer | system | staff, what }]\naudit_log += { actor, action, target }' },
    ],
  },
  {
    name: 'A super admin changes a role',
    staffOnly: true,
    steps: [
      { title: 'Super admin opens Roles', body: 'Built-in and custom roles are listed with how many accounts hold each one.',
        edges: ['officer>sso', 'sso>staffapi', 'staffapi>rbac'], payload: 'GET /api/admin/roles\nrequire_perm("roles.manage")' },
      { title: 'Permissions changed', body: 'Any role can be edited except the consumer role. Super admin must keep role management, and no role can both manage roles and move money.',
        edges: ['officer>desk', 'desk>staffapi', 'staffapi>rbac'], payload: 'PATCH /api/admin/roles/{slug} { permissions: [...] }\n400 if the rules above are broken' },
      { title: 'It applies on the next request', body: 'Permissions are read from the role on every request, so nobody needs to sign out. A changed built-in role can be reset to its default.',
        edges: ['staffapi>actions', 'actions>db'], payload: 'audit_log += role.update | role.reset\nPOST /api/admin/roles/{slug}/reset' },
    ],
  },
  {
    name: 'The system follows up on its own',
    staffOnly: true,
    steps: [
      { title: 'Next bill shows a misread', body: 'When next month\'s bill prints a previous reading lower than this bill\'s present reading, the meter was read too high. The case gets a suggested corrected reading.',
        edges: ['svc>review', 'review>engine', 'review>db'], payload: 'next.previous_reading < earlier.present_reading\ncase_suggestions += { corrected_present_reading }' },
      { title: 'A decision is drafted', body: 'The AE opens the case to a suggested decision with its reasons and evidence ticked. The engine prices it. The AE still records it.',
        edges: ['officer>desk', 'desk>staffapi', 'staffapi>review', 'review>engine'], payload: 'GET /api/review/cases/{ticket}/draft\n{ kind, reason_code, note, evidence, strength, why, preview }' },
      { title: 'Nobody has to chase', body: 'Every 15 minutes the scheduler reminds consumers after 3 days, closes unanswered requests after 7, and flags overdue cases, then escalates them a level up.',
        edges: ['sched>review', 'sched>sender', 'sender>meta', 'meta>consumer', 'sched>desk'], payload: 'run_reminders, run_lapses, run_overdue, run_digest\naudit actor = System' },
      { title: 'Billing closes the loop', body: 'When the DISCOM records show the revised amount was billed, the revision is marked applied and the consumer is told.',
        edges: ['sched>review', 'review>billing', 'actions>db'], payload: 'records[month].billed_amount == revised_amount (within Rs 1)\nrevision.applied_auto' },
      { title: 'Patterns reach managers', body: 'When corrected readings cluster in one section, the division gets an alert, so the fix can start with the meter reading round.',
        edges: ['sched>desk', 'officer>desk'], payload: 'corrected_reading decisions in 90 days >= 3\nalert pattern_section to the division' },
    ],
  },
];
