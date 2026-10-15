import { COMPLAINT_STATUSES, TRIAGES } from '@/features/complaints';
import { DISCOMS } from '@/shared/api/types';
import { useUrlState } from '@/shared/hooks/useUrlState';

import type { InboxQuery } from '../api/consoleApi';

const SORTS = ['priority', 'newest', 'oldest'] as const;
export type InboxFilterKey = 'status' | 'discom' | 'q' | 'triage';

export function useInboxParams() {
  const url = useUrlState();
  const query: InboxQuery = {
    page: url.page,
    pageSize: url.pageSize,
    status: url.pick('status', COMPLAINT_STATUSES),
    discom: url.pick('discom', DISCOMS),
    q: url.text('q').trim(),
    sort: url.pick('sort', SORTS) || 'priority',
    triage: url.pick('triage', TRIAGES),
    failed: url.text('failed') === '1',
  };
  return {
    query,
    setPage: url.setPage,
    setPageSize: url.setPageSize,
    setFilter: (key: InboxFilterKey, value: string) => url.update({ [key]: value }),
    setFailed: (on: boolean) => url.update({ failed: on ? '1' : null }),
    clearFilters: () => url.update({ status: null, discom: null, q: null, triage: null, failed: null }),
    setSort: (sort: InboxQuery['sort']) => url.update({ sort: sort === 'priority' ? null : sort }),
  };
}
