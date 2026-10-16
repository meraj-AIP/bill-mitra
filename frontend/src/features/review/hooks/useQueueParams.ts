import { useUrlState } from '@/shared/hooks/useUrlState';

import { REVIEW_STATES, type CaseQuery } from '../api/types';

const SORTS = ['oldest', 'newest'] as const;

/** The queue reads and writes every filter in the URL, so a link to a view opens that same view. */
export function useQueueParams() {
  const url = useUrlState();
  const query: CaseQuery = {
    page: url.page,
    pageSize: url.pageSize,
    state: url.pick('state', REVIEW_STATES),
    mine: url.text('mine') === '1',
    overdue: url.text('overdue') === '1',
    sectionId: url.text('section').trim(),
    q: url.text('q').trim(),
    // Oldest first by default: the case nearest its deadline is the one to open.
    sort: url.pick('sort', SORTS) || 'oldest',
  };
  return {
    query,
    setPage: url.setPage,
    setPageSize: url.setPageSize,
    setState: (state: string) => url.update({ state }),
    setFlag: (key: 'mine' | 'overdue', on: boolean) => url.update({ [key]: on ? '1' : null }),
    setSection: (sectionId: string | null) => url.update({ section: sectionId }),
    setQ: (q: string) => url.update({ q }),
    setSort: (sort: CaseQuery['sort']) => url.update({ sort: sort === 'oldest' ? null : sort }),
    filtered: Boolean(query.state || query.mine || query.overdue || query.sectionId || query.q),
    clear: () => url.update({ state: null, mine: null, overdue: null, section: null, q: null }),
  };
}
