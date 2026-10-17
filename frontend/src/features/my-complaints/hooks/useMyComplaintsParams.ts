import { useUrlState } from '@/shared/hooks/useUrlState';

import { MY_STATUSES, type MyListQuery } from '../api/types';

export function useMyComplaintsParams() {
  const url = useUrlState();
  const query: MyListQuery = { page: url.page, pageSize: url.pageSize, status: url.pick('status', MY_STATUSES) };
  return {
    query,
    setPage: url.setPage,
    setPageSize: url.setPageSize,
    setStatus: (status: string) => url.update({ status }),
  };
}
