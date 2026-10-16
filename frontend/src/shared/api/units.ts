import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { getJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import type { Unit, UnitKind } from '@/shared/api/types';

export interface UnitListQuery {
  /** Omit for the DISCOMs at the top of the tree. */
  parentId?: string | null;
  q?: string;
  kind?: UnitKind | '';
}

export function unitsQuery(query: UnitListQuery) {
  const params = new URLSearchParams();
  if (query.parentId) params.set('parent_id', query.parentId);
  if (query.q) params.set('q', query.q);
  if (query.kind) params.set('kind', query.kind);
  const text = params.toString();
  return {
    queryKey: queryKeys.unitList({ parentId: query.parentId ?? null, q: query.q ?? '', kind: query.kind ?? '' }),
    queryFn: ({ signal }: { signal: AbortSignal }) => getJson<Unit[]>(`/api/admin/units${text ? `?${text}` : ''}`, signal),
    staleTime: 60_000,
  };
}

/** GET /api/admin/units. Needs units.manage or accounts.manage, so callers pass enabled. */
export function useUnits(query: UnitListQuery, enabled = true) {
  return useQuery({ ...unitsQuery(query), placeholderData: keepPreviousData, enabled });
}
