import type { ComplaintType } from '../api/types';

export interface TypeGroup { category: string; label: string; types: ComplaintType[] }

// Billing is what most people come for, so it leads; any category the server adds later follows in its own order.
const ORDER = ['billing', 'meter', 'supply'];

const rank = (category: string) => {
  const i = ORDER.indexOf(category.toLowerCase());
  return i === -1 ? ORDER.length : i;
};

const title = (category: string) => category.charAt(0).toUpperCase() + category.slice(1).toLowerCase();

/** Types grouped by category, Billing first, keeping the server's order inside each group. */
export function groupTypes(types: ComplaintType[]): TypeGroup[] {
  const groups = new Map<string, ComplaintType[]>();
  for (const t of types) groups.set(t.category, [...(groups.get(t.category) ?? []), t]);
  return [...groups.entries()]
    .sort(([a], [b]) => rank(a) - rank(b))
    .map(([category, list]) => ({ category, label: list[0]?.category_label ?? title(category), types: list }));
}
