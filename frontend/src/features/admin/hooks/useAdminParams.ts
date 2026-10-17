import { useUrlState } from '@/shared/hooks/useUrlState';

import type { AccountQuery } from '../api/adminApi';
import { PARKED_KINDS, type OperationsQuery } from '../api/operationsApi';
import { AUDIT_ACTION_KEYS } from '../model/labels';

const ACTIVE = ['true', 'false'] as const;

export function useAccountsParams() {
  const url = useUrlState();
  const query: AccountQuery = {
    page: url.page,
    pageSize: url.pageSize,
    role: url.text('role').trim(),
    active: url.pick('active', ACTIVE),
    q: url.text('q').trim(),
  };
  return {
    query,
    setPage: url.setPage,
    setPageSize: url.setPageSize,
    setFilter: (key: 'role' | 'active' | 'q', value: string) => url.update({ [key]: value }),
    clearFilters: () => url.update({ role: null, active: null, q: null }),
  };
}

export function useAuditParams() {
  const url = useUrlState();
  return {
    page: url.page,
    pageSize: url.pageSize,
    action: url.pick('action', AUDIT_ACTION_KEYS),
    setPage: url.setPage,
    setPageSize: url.setPageSize,
    setAction: (action: string) => url.update({ action }),
  };
}

const SORTS = ['newest', 'oldest'] as const;

export function useOperationsParams() {
  const url = useUrlState();
  const query: OperationsQuery = { page: url.page, pageSize: url.pageSize, kind: url.pick('kind', PARKED_KINDS), sort: url.pick('sort', SORTS) };
  return {
    query,
    setPage: url.setPage,
    setPageSize: url.setPageSize,
    setKind: (kind: string) => url.update({ kind }),
    setSort: (sort: string) => url.update({ sort: sort === 'newest' ? null : sort }),
  };
}
