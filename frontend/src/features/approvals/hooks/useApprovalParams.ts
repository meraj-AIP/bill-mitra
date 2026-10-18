import { useUrlState } from '@/shared/hooks/useUrlState';

import { PROPOSAL_KINDS, PROPOSAL_STATES, type ApprovalsQuery } from '../api/approvalsApi';

export function useApprovalParams() {
  const url = useUrlState();
  const query: ApprovalsQuery = {
    page: url.page,
    pageSize: url.pageSize,
    kind: url.pick('kind', PROPOSAL_KINDS),
    state: url.pick('state', PROPOSAL_STATES),
  };
  return {
    query,
    setPage: url.setPage,
    setPageSize: url.setPageSize,
    setKind: (kind: string) => url.update({ kind }),
    setState: (state: string) => url.update({ state: state === 'pending' ? null : state }),
  };
}
