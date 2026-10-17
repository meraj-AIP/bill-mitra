import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import { IDEMPOTENT } from '@/shared/api/retry';
import type { Page } from '@/shared/api/types';

export const PARKED_KINDS = ['inbound', 'outbound', 'extract'] as const;
export type ParkedKind = (typeof PARKED_KINDS)[number];

/** A job that ran out of attempts. No message text: ticket, kind, attempts, error class and times only. */
export interface ParkedJob {
  id: string;
  kind: ParkedKind;
  ticket: string | null;
  attempts: number;
  last_error: string | null;
  created_at: string;
  failed_at: string;
}

export interface OperationsQuery {
  page: number;
  pageSize: number;
  kind: ParkedKind | '';
  sort: 'newest' | 'oldest' | '';
}

const BASE = '/api/admin/operations';
const jobPath = (job: Pick<ParkedJob, 'kind' | 'id'>) => `${BASE}/${job.kind}/${encodeURIComponent(job.id)}`;

export function useParkedJobs(query: OperationsQuery) {
  const params = new URLSearchParams({ page: String(query.page), page_size: String(query.pageSize) });
  if (query.kind) params.set('kind', query.kind);
  if (query.sort) params.set('sort', query.sort);
  return useQuery({
    queryKey: queryKeys.operationList(query),
    queryFn: ({ signal }) => getJson<Page<ParkedJob>>(`${BASE}?${params.toString()}`, signal),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });
}

function useRefresh() {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: queryKeys.operations });
    void client.invalidateQueries({ queryKey: queryKeys.health });
  };
}

/** Puts the job back in its queue. Not repeated on its own: a second requeue after a lost answer is not wanted. */
export function useRetryParked() {
  const onSuccess = useRefresh();
  return useMutation({ mutationFn: (job: ParkedJob) => sendJson<void>(`${jobPath(job)}/retry`), onSuccess });
}

/** Dismissing twice leaves the same result, so it may retry. */
export function useDismissParked() {
  const onSuccess = useRefresh();
  return useMutation({ ...IDEMPOTENT, mutationFn: (job: ParkedJob) => sendJson<void>(`${jobPath(job)}/dismiss`), onSuccess });
}
