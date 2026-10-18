import { can, canAny, isConsumer, PERMISSIONS, type Account, type Permission } from '@/features/auth';

export interface NavItem {
  to: string;
  label: string;
  /** One line under the label in a menu. */
  hint?: string;
}

/** Day to day work sits in the tabs; setup and oversight sit in one menu; help sits apart. */
export interface Nav {
  main: NavItem[];
  manage: NavItem[];
  help: NavItem;
}

interface Entry extends NavItem {
  /** Shown when the account holds any of these. The server checks again on every request. */
  any: readonly Permission[];
}

// The Assistant is the consumer's chat; staff with chat.preview see the same chat to know what consumers get.
export const ASSISTANT: readonly Permission[] = ['self.bills', 'chat.preview'];
export const CONSOLE: readonly Permission[] = ['console.view'];
export const COMPLAINTS: readonly Permission[] = ['complaints.view'];
export const REVIEW: readonly Permission[] = ['cases.view'];
// Approvals carry out replies, requests and decisions, so they need the permission to do those by hand.
export const APPROVALS: readonly Permission[] = ['complaints.reply', 'cases.decide'];
export const CONSUMER: readonly Permission[] = ['self.bills'];
// System health has no permission of its own; the server serves it to account managers.
export const HEALTH: readonly Permission[] = ['accounts.manage'];
// Parked failures show tickets and error classes only, so auditors may see them as well as account managers.
export const OPERATIONS: readonly Permission[] = ['audit.view', 'accounts.manage'];
// Alerts are for any staff account. self.bills is the one permission only consumers carry, so staff is everything else.
export const STAFF: readonly Permission[] = PERMISSIONS.filter((p) => p !== 'self.bills');

const MANAGE: Entry[] = [
  { to: '/admin/accounts', label: 'Accounts', hint: 'Staff sign ins, roles and units', any: ['accounts.manage'] },
  { to: '/admin/roles', label: 'Roles', hint: 'What each role is allowed to do', any: ['roles.manage'] },
  { to: '/admin/units', label: 'Units', hint: 'Circles, divisions, sections and EROs', any: ['units.manage'] },
  { to: '/admin/policy', label: 'Review policy', hint: 'AE limits, spike rules and time to decide', any: ['policy.manage'] },
  { to: '/admin/audit', label: 'Audit log', hint: 'Who changed what, and when', any: ['audit.view'] },
  { to: '/admin/health', label: 'System health', hint: 'Services on or off, and today\'s warnings', any: HEALTH },
  { to: '/admin/operations', label: 'Operations', hint: 'Queues, and messages that could not be sent or read', any: OPERATIONS },
];

const HOW: NavItem = { to: '/how-it-works', label: 'How it works' };

const strip = ({ to, label, hint }: Entry): NavItem => (hint ? { to, label, hint } : { to, label });

export function navFor(account: Pick<Account, 'permissions'>): Nav {
  const consumer = isConsumer(account);
  const review: Entry = { to: '/review', label: 'Review', any: REVIEW };
  const staff: Entry[] = [
    { to: '/console', label: 'Console', any: CONSOLE },
    { to: '/console/complaints', label: 'Complaints', any: COMPLAINTS },
    { to: '/approvals', label: 'Approvals', any: APPROVALS },
    { to: '/assistant', label: 'Consumer chat', any: ['chat.preview'] },
  ];
  // People who decide or approve start their day in the queue, so it comes first for them.
  const reviewer = can(account, 'cases.decide') || can(account, 'cases.approve');
  const main: Entry[] = consumer
    ? [{ to: '/', label: 'Dashboard', any: CONSUMER }, { to: '/complaints', label: 'Complaints', any: CONSUMER },
      { to: '/assistant', label: 'Assistant', any: CONSUMER }]
    : reviewer ? [review, ...staff] : [...staff, review];
  return {
    main: main.filter((e) => canAny(account, e.any)).map(strip),
    manage: consumer ? [] : MANAGE.filter((e) => canAny(account, e.any)).map(strip),
    help: HOW,
  };
}

/** The longest matching path wins, so /console/complaints/BM-1 lights up Complaints, not Console. */
export function currentTab(items: NavItem[], pathname: string): string | false {
  const hasHome = items.some((n) => n.to === '/');
  if (pathname.startsWith('/bills')) return hasHome ? '/' : false;
  const match = items
    .filter((n) => n.to !== '/' && (pathname === n.to || pathname.startsWith(`${n.to}/`)))
    .sort((a, b) => b.to.length - a.to.length)[0];
  if (match) return match.to;
  return pathname === '/' && hasHome ? '/' : false;
}
