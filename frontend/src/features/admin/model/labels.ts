export const AUDIT_ACTIONS: Record<string, string> = {
  'auth.login': 'Signed in',
  'account.register': 'Registered',
  'account.password_change': 'Changed password',
  'account.create': 'Created an account',
  'account.update': 'Changed an account',
  'account.reset_password': 'Reset a password',
  'account.bootstrap_admin': 'First admin created',
  'account.delete_self': 'Deleted own account',
  'complaint.reply': 'Replied to a complaint',
  'complaint.status': 'Changed a complaint status',
  'complaint.export': 'Exported complaints',
  'role.create': 'Created a role',
  'role.update': 'Changed a role',
  'role.delete': 'Deleted a role',
  'unit.create': 'Added a unit',
  'unit.update': 'Changed a unit',
  'unit.import': 'Imported units',
  'unit.map': 'Mapped a section name',
  'policy.update': 'Changed review policy',
  'case.route': 'Routed a case',
  'case.assign': 'Reassigned a case',
  'case.request': 'Asked a consumer for information',
  'case.unmask': 'Viewed a full service number',
  'decision.create': 'Recorded a decision',
  'decision.approve': 'Approved a decision',
  'decision.reject': 'Rejected a decision',
  'decision.withdraw': 'Withdrew a decision',
  'decision.applied': 'Marked a revision applied',
  'revision.export': 'Exported revisions',
};

/** Built-in role names, for audit lines written before the role list loads. Custom roles show their slug. */
export const BUILTIN_ROLE_NAME: Record<string, string> = {
  super_admin: 'Super admin',
  admin: 'Admin',
  officer: 'DISCOM officer',
  section_ae: 'Section AE',
  billing_approver: 'Billing approver',
  auditor: 'Auditor',
  consumer: 'Consumer',
};

export const AUDIT_ACTION_KEYS = Object.keys(AUDIT_ACTIONS);

const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';

/** 14 characters without look-alikes (0/O, 1/l/I), so it can be read out over the phone. */
export function generatePassword(length = 14): string {
  const bytes = new Uint32Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => ALPHABET[b % ALPHABET.length]).join('');
}

export const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
