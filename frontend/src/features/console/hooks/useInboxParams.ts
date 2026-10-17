import { COMPLAINT_STATUSES, PRIORITIES, SOURCES, TRIAGES } from '@/features/complaints';
import { DISCOMS } from '@/shared/api/types';
import { useUrlState } from '@/shared/hooks/useUrlState';

import type { InboxQuery } from '../api/consoleApi';

const SORTS = ['priority', 'newest', 'oldest'] as const;
export type InboxFilterKey = 'status' | 'discom' | 'q' | 'triage' | 'type' | 'priority' | 'source';
const CLEARED = { status: null, discom: null, q: null, triage: null, failed: null, type: null, priority: null, source: null };
// Type codes come from the server catalogue, so the URL value is only shape checked here.
const TYPE_CODE = /^[a-z_]{1,40}$/;

export function useInboxParams() {
  const url = useUrlState();
  const type = url.text('type');
  const query: InboxQuery = {
    page: url.page,
    pageSize: url.pageSize,
    status: url.pick('status', COMPLAINT_STATUSES),
    discom: url.pick('discom', DISCOMS),
    q: url.text('q').trim(),
    sort: url.pick('sort', SORTS) || 'priority',
    triage: url.pick('triage', TRIAGES),
    failed: url.text('failed') === '1',
    type: TYPE_CODE.test(type) ? type : '',
    priority: url.pick('priority', PRIORITIES),
    source: url.pick('source', SOURCES),
  };
  const filtered = Boolean(query.status || query.discom || query.q || query.triage || query.failed || query.type
    || query.priority || query.source);
  return {
    query,
    filtered,
    setPage: url.setPage,
    setPageSize: url.setPageSize,
    setFilter: (key: InboxFilterKey, value: string) => url.update({ [key]: value }),
    setFailed: (on: boolean) => url.update({ failed: on ? '1' : null }),
    clearFilters: () => url.update(CLEARED),
    setSort: (sort: InboxQuery['sort']) => url.update({ sort: sort === 'priority' ? null : sort }),
  };
}
