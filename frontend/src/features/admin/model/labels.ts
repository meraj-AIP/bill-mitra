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
