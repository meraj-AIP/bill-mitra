import type { AuditEntry } from '../api/adminApi';
import { BUILTIN_ROLE_NAME } from './labels';

const DELIVERY: Record<string, string> = {
  stored: 'Delivered in the web app',
  sent: 'Sent on WhatsApp',
  failed: 'Not delivered',
};

const FIELD: Record<string, string> = { name: 'name', role: 'role', discom: 'DISCOM', scopes: 'units', active: 'active status' };

/** The server writes short machine notes ("delivery sent", "role=officer", "name,role"); say them in words. */
export function auditDetail(e: AuditEntry): string {
  if (!e.detail) return '';
  if (e.action === 'account.update') {
    return `Changed ${e.detail.split(',').map((f) => FIELD[f] ?? f).join(', ')}`;
  }
  return e.detail.split(', ').map((part) => {
    const delivery = /^delivery (\w+)$/.exec(part);
    if (delivery) return DELIVERY[delivery[1]!] ?? part;
    const role = /^role=(\w+)$/.exec(part)?.[1];
    if (role) return `As ${BUILTIN_ROLE_NAME[role] ?? role}`;
    return part;
  }).join('. ');
}

/** An account target that still reads as its raw id means the account has since been removed. */
export function auditTarget(e: AuditEntry): string {
  if (!e.target) return '';
  const label = e.target_label ?? e.target;
  if (label === e.target && /^(account|auth)\./.test(e.action)) return 'Removed account';
  return label;
}
