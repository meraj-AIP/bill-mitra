import type { Account } from '../api/authApi';

/** The fixed catalogue from the review contract. Typed so a misspelt check fails to compile. */
export const PERMISSIONS = [
  'roles.manage', 'units.manage', 'policy.manage', 'accounts.manage',
  'console.view', 'complaints.view', 'complaints.reply', 'complaints.assign',
  'cases.view', 'cases.request_info', 'cases.decide', 'cases.reassign', 'cases.approve', 'cases.mark_applied', 'cases.export',
  'consumer.unmask', 'audit.view', 'chat.preview', 'self.bills',
] as const;

export type Permission = (typeof PERMISSIONS)[number];

type Holder = Pick<Account, 'permissions'> | null | undefined;

export function can(account: Holder, permission: Permission): boolean {
  return Boolean(account?.permissions.includes(permission));
}

export function canAny(account: Holder, permissions: readonly Permission[]): boolean {
  return permissions.some((p) => can(account, p));
}

/** Consumers hold self.bills and nothing staff-like; it is the one permission only they carry. */
export function isConsumer(account: Holder): boolean {
  return can(account, 'self.bills');
}

/** Where a person lands after sign in: their bills, their review queue, or the console. */
export function landingFor(account: Holder): string {
  if (!account) return '/login';
  if (isConsumer(account)) return '/';
  if (can(account, 'cases.view') && canAny(account, ['cases.decide', 'cases.approve'])) return '/review';
  if (can(account, 'console.view')) return '/console';
  if (can(account, 'cases.view')) return '/review';
  if (can(account, 'accounts.manage')) return '/admin/accounts';
  return '/how-it-works';
}

/** Both DISCOM units in scope means the whole state; otherwise the scope names, as the server sent them. */
export function scopeLabel(account: Pick<Account, 'scopes'> | null | undefined): string | null {
  const scopes = account?.scopes ?? [];
  if (scopes.length === 0) return null;
  if (scopes.filter((s) => s.kind === 'discom').length >= 2) return 'All of Telangana';
  return scopes.map((s) => s.name).join(', ');
}

/** True when the account sees more than one DISCOM, so a DISCOM filter means something. */
export function spansDiscoms(account: Pick<Account, 'scopes'> | null | undefined): boolean {
  return (account?.scopes ?? []).filter((s) => s.kind === 'discom').length >= 2;
}
