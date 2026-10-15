import type { Role } from '@/features/auth';

export const CONSUMER: readonly Role[] = ['consumer'];
// Admins can try the chat to see what consumers get; officers have no use for it.
export const ASSISTANT: readonly Role[] = ['consumer', 'admin'];
export const STAFF: readonly Role[] = ['officer', 'admin'];
export const ADMIN: readonly Role[] = ['admin'];
export const EVERYONE: readonly Role[] = ['consumer', 'officer', 'admin'];

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

const HOW: NavItem = { to: '/how-it-works', label: 'How it works' };

const NAV: Record<Role, Nav> = {
  consumer: {
    main: [{ to: '/', label: 'Dashboard' }, { to: '/assistant', label: 'Assistant' }],
    manage: [],
    help: HOW,
  },
  officer: {
    main: [{ to: '/console', label: 'Console' }, { to: '/console/complaints', label: 'Complaints' }],
    manage: [],
    help: HOW,
  },
  admin: {
    main: [
      { to: '/console', label: 'Console' },
      { to: '/console/complaints', label: 'Complaints' },
      { to: '/assistant', label: 'Consumer chat' },
    ],
    manage: [
      { to: '/admin/accounts', label: 'Accounts', hint: 'Staff sign ins, roles and DISCOMs' },
      { to: '/admin/audit', label: 'Audit log', hint: 'Who changed what, and when' },
      { to: '/admin/health', label: 'System health', hint: 'Services on or off, and today\'s warnings' },
    ],
    help: HOW,
  },
};

export function navFor(role: Role): Nav {
  return NAV[role];
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
