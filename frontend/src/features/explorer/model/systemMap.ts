export type NodeStatus = 'built' | 'planned' | 'external';

export interface SystemNode {
  id: string;
  lane: number;
  y: number;
  title: string;
  code: string;
  status: NodeStatus;
  notes: string[];
}

export const LANES = ['People', 'Channels', 'Edge', 'Core', 'Rules and AI', 'Data and systems'];
export const NODE_W = 160;
export const NODE_H = 50;
export const MAP_W = 1120;
export const MAP_H = 540;
export const LANE_X = [16, 200, 384, 568, 752, 944];

export const NODES: SystemNode[] = [
  { id: 'consumer', lane: 0, y: 60, title: 'Consumer', code: 'WhatsApp or the website', status: 'built',
    notes: ['Sends a photo, PDF, voice note or text in Telugu, English, Hindi or Urdu', 'Never shares a name or address; the bill does not need one',
      'Taps Bill looks wrong to have a bill reviewed, and only ever sees neutral updates: received, we need your bills, revised, no change'] },
  { id: 'officer', lane: 0, y: 390, title: 'DISCOM staff', code: 'six roles, by unit', status: 'built',
    notes: ['Each account has one role and one unit: DISCOM, circle, division, sub-division, section or ERO',
      'They see only their unit and everything below it', 'An admin can add custom roles and change any built-in role except the consumer one'] },
  { id: 'meta', lane: 1, y: 30, title: 'WhatsApp Cloud API', code: 'Meta Graph API', status: 'external',
    notes: ['Hosts the verified business number and delivers messages to our webhook',
      'Free form replies only within 24 hours of the consumer\'s last message; after that, approved templates'] },
  { id: 'web', lane: 1, y: 120, title: 'Bill Mitra web', code: 'frontend/src/features', status: 'built',
    notes: ['Dashboard, Assistant, Console, Admin and this page', 'The Assistant streams the same turns WhatsApp gets'] },
  { id: 'desk', lane: 1, y: 390, title: 'Staff workspace', code: 'console, review, admin', status: 'built',
    notes: ['Console: summary and complaint inbox', 'Review: wrong-reading cases with the evidence pack, decision panel and timeline',
      'Admin: accounts, roles, units, review policy and the audit log', 'Menus show only what the role can open; the server refuses the rest anyway'] },
  { id: 'sso', lane: 1, y: 470, title: 'Sign in', code: 'api/auth, api/deps', status: 'built',
    notes: ['Password sign in, rate limited, with an HTTP-only session cookie',
      'The role\'s permissions are read fresh on every request, so a role change takes effect at once', 'Planned: DISCOM directory sign in'] },
  { id: 'ingress', lane: 2, y: 30, title: 'Webhook ingress', code: 'channels/whatsapp', status: 'built',
    notes: ['Checks X-Hub-Signature-256 with the app secret', 'Turns the phone number into a one way pseudonym and forgets the number',
      'Answers Meta fast so it does not retry'] },
  { id: 'queue', lane: 2, y: 120, title: 'Job queue', code: 'workers', status: 'planned',
    notes: ['Takes every turn and every outbound send, with retries', 'Keeps bill day bursts from blocking the webhook'] },
  { id: 'sender', lane: 2, y: 210, title: 'WhatsApp sender', code: 'whatsapp/client.py', status: 'built',
    notes: ['Uploads media and converts voice to OGG Opus', 'Payloads built from core/messages.py, limits checked before sending'] },
  { id: 'staffapi', lane: 2, y: 390, title: 'Staff API', code: 'api/*, require_perm', status: 'built',
    notes: ['Every route asks for a permission first, then checks the record sits inside the account\'s unit',
      'api/console, api/complaints, api/review, api/admin', 'A route outside the role gives 403; signed out gives 401'] },
  { id: 'svc', lane: 3, y: 40, title: 'Conversation service', code: 'core/service + flows', status: 'built',
    notes: ['handle(inbound, emit) for every channel', 'Flows: bill, question, meter, complaint, analysis', 'Each step traced: ai, rules or channel'] },
  { id: 'review', lane: 3, y: 130, title: 'Bill review', code: 'flows/cases, review', status: 'built',
    notes: ['Spots a spike against the consumer\'s own history and opens a case', 'Routes it to the right section from the section printed on the bill',
      'Builds the evidence pack and asks for up to three missing monthly bills', 'Prices a corrected reading with the engine; the revised amount becomes the final bill'] },
  { id: 'sched', lane: 3, y: 220, title: 'Automation', code: 'services/scheduler.py', status: 'built',
    notes: ['Runs every 15 minutes: reminds consumers, closes requests nobody answers, flags and escalates overdue cases',
      'A daily digest for each AE, and alerts when misreads cluster in one section',
      'Marks a revision applied when the DISCOM records show it was billed', 'Never decides or approves a case'] },
  { id: 'agent', lane: 3, y: 315, title: 'Staff assistant', code: 'staff/agent', status: 'planned',
    notes: ['Tools: run_metric, list_tickets, open_bill, propose_action', 'Never sees SQL or the scope filter', 'Proposes actions; a person confirms them'] },
  { id: 'actions', lane: 3, y: 430, title: 'Actions and audit', code: 'decisions, audit log', status: 'built',
    notes: ['Replies, case decisions, approvals, marking applied, unmasking with a reason, role, unit and policy changes',
      'Each one written to the audit log with who did it', 'The case timeline shows consumer, system and staff steps in order'] },
  { id: 'engine', lane: 4, y: 30, title: 'Tariff engine', code: 'domain/tariff', status: 'built',
    notes: ['Every rupee figure, unit count and date', 'Picks the tariff version in force for the bill month'] },
  { id: 'guard', lane: 4, y: 120, title: 'Number guard', code: 'conversation/guard.py', status: 'built',
    notes: ['Rejects model text with a figure the facts do not hold', 'Planned: guards staff assistant answers too'] },
  { id: 'prov', lane: 4, y: 210, title: 'AI providers', code: 'OpenAI, Soniox', status: 'external',
    notes: ['OpenAI reads the photo and words replies', 'Soniox speaks the reply and transcribes voice notes', 'Each is optional; health says when one is off'] },
  { id: 'rbac', lane: 4, y: 420, title: 'Access rules', code: 'domain/rbac.py', status: 'built',
    notes: ['The permission catalogue and the built-in roles', 'Nobody approves or marks applied their own decision',
      'A role that manages roles never also moves money', 'Admin always keeps role management; the consumer role is fixed'] },
  { id: 'cat', lane: 4, y: 310, title: 'Metric catalogue', code: 'staff/metrics', status: 'planned',
    notes: ['Name, definition, SQL, roles and drill target for each metric', 'The only way screens, alerts and the assistant get a number'] },
  { id: 'db', lane: 5, y: 20, title: 'Database', code: 'store/*', status: 'built',
    notes: ['SQLite today, Postgres for the pilot', 'All SQL lives in store/, so the move is one folder'] },
  { id: 'media', lane: 5, y: 88, title: 'Media store', code: 'store/media.py', status: 'built',
    notes: ['Content addressed photos, voice notes and charts', 'Pilot: object storage, encrypted, deleted on STOP'] },
  { id: 'billing', lane: 5, y: 156, title: 'DISCOM billing records', code: 'billing_records.py', status: 'external',
    notes: ['The connector is built: set BILLING_RECORDS_URL and earlier months for a service number join the evidence pack, tagged DISCOM',
      'Not connected on this server, so the pack says so instead of guessing'] },
  { id: 'crm', lane: 5, y: 224, title: '1912 grievance', code: 'ticket sync', status: 'external',
    notes: ['Register tickets and sync status both ways', 'Not connected yet; tickets stay in Bill Mitra'] },
  { id: 'tgerc', lane: 5, y: 292, title: 'TGERC orders', code: 'tariff/tables.py', status: 'built',
    notes: ['Each order is a new version with its dates', 'Old versions are never edited'] },
  { id: 'hr', lane: 5, y: 360, title: 'Org tree and staff', code: 'DISCOM HR', status: 'external',
    notes: ['Units live in Bill Mitra today, added by hand or imported from a CSV', 'Planned: a feed of who sits where from DISCOM HR'] },
  { id: 'obs', lane: 5, y: 428, title: 'Logs and metrics', code: 'no personal data', status: 'planned',
    notes: ['Latency per step and provider, guard failures, error rates', 'Alerts to the operations team'] },
];

export const NODE_BY_ID = new Map(NODES.map((n) => [n.id, n]));

export const EDGES = [
  'consumer>meta', 'consumer>web', 'meta>ingress', 'ingress>queue', 'queue>svc', 'web>svc', 'svc>media', 'svc>prov', 'svc>review',
  'review>engine', 'review>billing', 'review>db', 'review>sender', 'staffapi>rbac', 'staffapi>review',
  'svc>engine', 'tgerc>engine', 'svc>guard', 'svc>sender', 'queue>sender', 'sender>meta', 'meta>consumer', 'svc>db', 'svc>crm',
  'sched>cat', 'cat>db', 'sched>desk', 'sched>review', 'sched>sender', 'officer>sso', 'sso>staffapi', 'hr>staffapi', 'officer>desk', 'desk>staffapi',
  'staffapi>agent', 'agent>cat', 'agent>prov', 'agent>guard', 'staffapi>actions', 'actions>db', 'actions>crm', 'actions>queue', 'svc>obs',
];

export function nodeX(node: SystemNode): number {
  return LANE_X[node.lane] ?? 0;
}

/** Curves between lanes, straight lines inside one. */
export function edgePath(edge: string): string {
  const [from, to] = edge.split('>').map((id) => NODE_BY_ID.get(id ?? ''));
  if (!from || !to) return '';
  const ax = nodeX(from);
  const bx = nodeX(to);
  if (ax === bx) {
    const up = to.y < from.y;
    return `M${ax + NODE_W / 2} ${up ? from.y : from.y + NODE_H} L${bx + NODE_W / 2} ${up ? to.y + NODE_H : to.y}`;
  }
  const forward = bx > ax;
  const x1 = forward ? ax + NODE_W : ax;
  const x2 = forward ? bx : bx + NODE_W;
  const y1 = from.y + NODE_H / 2;
  const y2 = to.y + NODE_H / 2;
  const mid = (x1 + x2) / 2;
  return `M${x1} ${y1} C${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`;
}
