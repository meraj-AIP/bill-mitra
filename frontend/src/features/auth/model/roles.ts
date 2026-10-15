import type { Role } from '../api/authApi';

export const ROLE_LABEL: Record<Role, string> = {
  admin: 'Administrator',
  officer: 'DISCOM officer',
  consumer: 'Consumer',
};

export function landingFor(role: Role): string {
  return role === 'consumer' ? '/' : '/console';
}

/** Only same-site paths are followed after sign in, so a crafted link cannot send people elsewhere. */
export function safeNext(next: string | null): string | null {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/login') || next.startsWith('/register')) {
    return null;
  }
  return next;
}

export const MOBILE_PATTERN = /^[6-9]\d{9}$/;
export const MIN_PASSWORD = 8;

/** People type their mobile with spaces or a +91 prefix; the server wants the bare 10 digits. */
export function normaliseLogin(value: string): string {
  const trimmed = value.trim();
  const digits = trimmed.replace(/[\s-]/g, '');
  const match = /^(?:\+?91|0)?([6-9]\d{9})$/.exec(digits);
  return match?.[1] ?? trimmed;
}

export function passwordProblem(password: string): string | null {
  return password.length < MIN_PASSWORD ? `Use at least ${MIN_PASSWORD} characters.` : null;
}
