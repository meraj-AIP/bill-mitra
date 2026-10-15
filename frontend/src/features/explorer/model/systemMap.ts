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
    notes: ['Sends a photo, PDF, voice note or text in Telugu, English, Hindi or Urdu', 'Never shares a name or address; the bill does not need one'] },
  { id: 'officer', lane: 0, y: 390, title: 'DISCOM staff', code: 'officer, admin', status: 'built',
    notes: ['Officers today see their own DISCOM; admins see all', 'Planned: section AE, division DE, billing AAO, 1912 agent and HQ roles'] },
  { id: 'meta', lane: 1, y: 30, title: 'WhatsApp Cloud API', code: 'Meta Graph API', status: 'external',
    notes: ['Hosts the verified business number and delivers messages to our webhook',
      'Free form replies only within 24 hours of the consumer\'s last message; after that, approved templates'] },
  { id: 'web', lane: 1, y: 120, title: 'Bill Mitra web', code: 'frontend/src/features', status: 'built',
    notes: ['Dashboard, Assistant, Console, Admin and this page', 'The Assistant streams the same turns WhatsApp gets'] },
  { id: 'desk', lane: 1, y: 390, title: 'Staff workspace', code: 'console, admin, desk', status: 'built',
    notes: ['Today: Console with summary and complaint inbox, Admin with accounts and audit log',
      'Planned: drill down to the bill, live chats, alerts, assistant, field requests'] },
  { id: 'sso', lane: 1, y: 470, title: 'Sign in', code: 'api/auth, api/deps', status: 'built',
    notes: ['Today: password sign in with roles admin, officer and consumer, rate limited',
      'Planned: DISCOM directory sign in, with the org tree setting scope'] },
  { id: 'ingress', lane: 2, y: 30, title: 'Webhook ingress', code: 'channels/whatsapp', status: 'built',
    notes: ['Checks X-Hub-Signature-256 with the app secret', 'Turns the phone number into a one way pseudonym and forgets the number',
      'Answers Meta fast so it does not retry'] },
  { id: 'queue', lane: 2, y: 120, title: 'Job queue', code: 'workers', status: 'planned',
    notes: ['Takes every turn and every outbound send, with retries', 'Keeps bill day bursts from blocking the webhook'] },
  { id: 'sender', lane: 2, y: 210, title: 'WhatsApp sender', code: 'whatsapp/client.py', status: 'built',
    notes: ['Uploads media and converts voice to OGG Opus', 'Payloads built from core/messages.py, limits checked before sending'] },
  { id: 'staffapi', lane: 2, y: 390, title: 'Staff API', code: 'api/console, complaints, admin', status: 'built',
    notes: ['Every route checks the role first, then the DISCOM scope', 'Planned: /api/staff/metrics/{name} for every number in the workspace'] },
  { id: 'svc', lane: 3, y: 70, title: 'Conversation service', code: 'core/service + flows', status: 'built',
    notes: ['handle(inbound, emit) for every channel', 'Flows: bill, question, meter, complaint, analysis', 'Each step traced: ai, rules or channel'] },
  { id: 'sched', lane: 3, y: 210, title: 'Alerts and digests', code: 'staff/scheduler', status: 'planned',
    notes: ['Runs catalogue metrics on a timer and raises alerts against thresholds', 'Builds the weekly digest per division'] },
  { id: 'agent', lane: 3, y: 310, title: 'Staff assistant', code: 'staff/agent', status: 'planned',
    notes: ['Tools: run_metric, list_tickets, open_bill, propose_action', 'Never sees SQL or the scope filter', 'Proposes actions; a person confirms them'] },
  { id: 'actions', lane: 3, y: 430, title: 'Actions and audit', code: 'complaints, accounts', status: 'built',
    notes: ['Today: reply, status change and account changes, each written to the audit log',
      'Planned: assign, unmask with a reason, broadcasts with a second approver'] },
  { id: 'engine', lane: 4, y: 30, title: 'Tariff engine', code: 'domain/tariff', status: 'built',
    notes: ['Every rupee figure, unit count and date', 'Picks the tariff version in force for the bill month'] },
  { id: 'guard', lane: 4, y: 120, title: 'Number guard', code: 'conversation/guard.py', status: 'built',
    notes: ['Rejects model text with a figure the facts do not hold', 'Planned: guards staff assistant answers too'] },
  { id: 'prov', lane: 4, y: 210, title: 'AI providers', code: 'OpenAI, Sarvam, Soniox', status: 'external',
    notes: ['OpenAI reads the photo and words replies', 'Sarvam speaks Telugu, Soniox transcribes voice notes', 'Each is optional; health says when one is off'] },
  { id: 'cat', lane: 4, y: 310, title: 'Metric catalogue', code: 'staff/metrics', status: 'planned',
    notes: ['Name, definition, SQL, roles and drill target for each metric', 'The only way screens, alerts and the assistant get a number'] },
  { id: 'db', lane: 5, y: 20, title: 'Database', code: 'store/*', status: 'built',
    notes: ['SQLite today, Postgres for the pilot', 'All SQL lives in store/, so the move is one folder'] },
  { id: 'media', lane: 5, y: 88, title: 'Media store', code: 'store/media.py', status: 'built',
    notes: ['Content addressed photos, voice notes and charts', 'Pilot: object storage, encrypted, deleted on STOP'] },
  { id: 'billing', lane: 5, y: 156, title: 'DISCOM billing API', code: 'TGSPDCL, TGNPDCL', status: 'external',
    notes: ['12 months of history for a service number, read only after consent', 'Not connected yet'] },
  { id: 'crm', lane: 5, y: 224, title: '1912 grievance', code: 'ticket sync', status: 'external',
    notes: ['Register tickets and sync status both ways', 'Not connected yet; tickets stay in Bill Mitra'] },
  { id: 'tgerc', lane: 5, y: 292, title: 'TGERC orders', code: 'tariff/tables.py', status: 'built',
    notes: ['Each order is a new version with its dates', 'Old versions are never edited'] },
  { id: 'hr', lane: 5, y: 360, title: 'Org tree and staff', code: 'DISCOM HR', status: 'external',
    notes: ['Circle, division, sub-division, section and who sits where', 'Needed to scope staff below DISCOM level'] },
  { id: 'obs', lane: 5, y: 428, title: 'Logs and metrics', code: 'no personal data', status: 'planned',
    notes: ['Latency per step and provider, guard failures, error rates', 'Alerts to the operations team'] },
];

export const NODE_BY_ID = new Map(NODES.map((n) => [n.id, n]));

export const EDGES = [
  'consumer>meta', 'consumer>web', 'meta>ingress', 'ingress>queue', 'queue>svc', 'web>svc', 'svc>media', 'svc>prov', 'svc>billing',
  'svc>engine', 'tgerc>engine', 'svc>guard', 'svc>sender', 'queue>sender', 'sender>meta', 'meta>consumer', 'svc>db', 'svc>crm',
  'sched>cat', 'cat>db', 'sched>desk', 'officer>sso', 'sso>staffapi', 'hr>staffapi', 'officer>desk', 'desk>staffapi',
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
