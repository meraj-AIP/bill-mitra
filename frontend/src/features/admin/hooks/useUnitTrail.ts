import { useQueries } from '@tanstack/react-query';

import type { Unit } from '@/shared/api/types';
import { unitsQuery } from '@/shared/api/units';
import { useUrlState } from '@/shared/hooks/useUrlState';

/**
 * Where the person is in the unit tree, kept in the URL as the ids from the DISCOM down.
 * There is no single-unit endpoint, so each step's name is read from its parent's child list,
 * which is already cached from the way down.
 */
export function useUnitTrail() {
  const url = useUrlState();
  const ids = url.text('at').split(',').filter(Boolean).slice(0, 5);
  const levels = useQueries({
    queries: [null, ...ids].map((parentId) => unitsQuery({ parentId })),
  });
  const trail: Unit[] = [];
  for (const [i, id] of ids.entries()) {
    const found = levels[i]?.data?.find((u) => u.id === id);
    if (!found) break;
    trail.push(found);
  }
  const current = trail.at(-1) ?? null;
  const children = levels[trail.length];
  return {
    trail,
    current,
    /** Still resolving the path from the URL. */
    resolving: levels.slice(0, ids.length).some((l) => l.isPending),
    lost: ids.length > 0 && levels.slice(0, ids.length).every((l) => !l.isPending) && trail.length < ids.length,
    children: children?.data,
    childrenError: children?.error ?? null,
    refetch: () => void children?.refetch(),
    open: (unit: Unit) => url.update({ at: [...trail.map((u) => u.id), unit.id].join(',') }),
    goTo: (depth: number) => url.update({ at: trail.slice(0, depth).map((u) => u.id).join(',') || null }),
  };
}
