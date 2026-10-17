import { useUrlState } from '@/shared/hooks/useUrlState';

import type { AlertQuery } from '../api/types';

export function useAlertsParams() {
  const url = useUrlState();
  const query: AlertQuery = { page: url.page, pageSize: url.pageSize, unread: url.text('unread') === '1' };
  return {
    query,
    setPage: url.setPage,
    setPageSize: url.setPageSize,
    setUnread: (on: boolean) => url.update({ unread: on ? '1' : null }),
  };
}
