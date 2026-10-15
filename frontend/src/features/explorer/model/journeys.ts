export interface JourneyStep {
  title: string;
  body: string;
  edges: string[];
  payload: string;
  planned?: boolean;
}

export interface Journey {
  name: string;
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
    steps: [
      { title: 'Consumer taps Raise complaint', body: 'The complaint is built from the checked bill, so it carries the engine figures.',
        edges: ['consumer>meta', 'meta>ingress', 'ingress>queue', 'queue>svc'], payload: 'button_reply id="complain" -> intent complain' },
      { title: 'Ticket opened', body: 'Stored in Bill Mitra with its DISCOM. With 1912 access it is registered there too.',
        edges: ['svc>db', 'svc>crm'], payload: 'complaints += { ticket, discom, issue, amount, status: "Open" }' },
      { title: 'Alert reaches the officer', body: 'The scheduler watches tickets close to their SLA and tells the right officer.', planned: true,
        edges: ['sched>cat', 'cat>db', 'sched>desk'], payload: 'alert sla_risk(scope) -> tickets due within 24 hours' },
      { title: 'Officer signs in', body: 'Sign in sets the role and the DISCOM. With the org tree, scope narrows to division or section.',
        edges: ['officer>sso', 'sso>staffapi', 'hr>staffapi'], payload: 'account.role = "officer", account.discom -> every query filtered' },
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
];
