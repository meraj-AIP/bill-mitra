import type { PermissionInfo } from '../api/rolesApi';

/** What each permission lets a person do, said the way an administrator would explain it to a colleague. */
export const PERMISSION_HINT: Record<string, string> = {
  'roles.manage': 'Create roles and change what any role can do, built-in ones included.',
  'units.manage': 'Add and edit circles, divisions, sections and EROs, import them from a file, and map new section names.',
  'policy.manage': 'Set each DISCOM\'s AE limit, spike rules and the days allowed to decide.',
  'accounts.manage': 'Create and edit staff accounts inside their own units.',
  'console.view': 'See the department console: bills read, questions asked and complaints raised.',
  'complaints.view': 'Open the complaints inbox and read each complaint.',
  'complaints.reply': 'Reply to consumers on a complaint.',
  'complaints.assign': 'Move a complaint to another officer.',
  'cases.view': 'See wrong-reading cases in their units.',
  'cases.request_info': 'Ask the consumer for earlier bills, a meter photo or a note.',
  'cases.decide': 'Record a decision on a case: bill correct, corrected reading or a reduction.',
  'cases.reassign': 'Move a case to another person in the same units.',
  'cases.approve': 'Approve or reject a decision that needs a second person.',
  'cases.mark_applied': 'Confirm a revision has been entered in the DISCOM billing system.',
  'cases.export': 'Download the revisions as a CSV file.',
  'consumer.unmask': 'See a full service number on an open case. Every view is recorded.',
  'audit.view': 'Read the audit log for their units.',
  'chat.preview': 'Try the consumer chat, to see what consumers get.',
  'self.bills': 'Consumers only: their own bills, chat and review requests.',
};

// Mirrors rbac.NOT_WITH_ROLE_MANAGEMENT: whoever shapes roles never also moves money or acts as a consumer.
const NOT_WITH_ROLES = new Set(['cases.decide', 'cases.approve', 'cases.mark_applied', 'self.bills']);

/** The contract's separation of duties rule, checked before the server refuses it. */
export function separationProblem(permissions: string[]): string | null {
  if (!permissions.includes('roles.manage')) return null;
  return permissions.some((p) => NOT_WITH_ROLES.has(p))
    ? 'A role that manages roles cannot also decide, approve or mark revisions applied. Untick those or untick Manage roles.'
    : null;
}

/** Consumers' own permission is never granted to a staff role. */
export const STAFF_ONLY_HIDDEN = new Set(['self.bills']);

export function groupCatalog(catalog: PermissionInfo[], hidden: ReadonlySet<string> = STAFF_ONLY_HIDDEN): Array<{ group: string; items: PermissionInfo[] }> {
  const groups = new Map<string, PermissionInfo[]>();
  for (const p of catalog) {
    if (hidden.has(p.code)) continue;
    groups.set(p.group, [...(groups.get(p.group) ?? []), p]);
  }
  return [...groups].map(([group, items]) => ({ group, items }));
}
