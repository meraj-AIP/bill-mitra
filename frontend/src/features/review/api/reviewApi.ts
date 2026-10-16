import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';

import type { CaseDetail, CasePageResult, CaseQuery, NewDecision, Preview, RequestKind, SectionOption } from './types';

const casePath = (ticket: string) => `/api/review/cases/${encodeURIComponent(ticket)}`;
const decisionPath = (id: number) => `/api/review/decisions/${id}`;

function listParams(query: CaseQuery) {
  const params = new URLSearchParams({ page: String(query.page), page_size: String(query.pageSize), sort: query.sort });
  if (query.state) params.set('state', query.state);
  if (query.mine) params.set('mine', 'true');
  if (query.overdue) params.set('overdue', 'true');
  if (query.sectionId) params.set('section_id', query.sectionId);
  if (query.q) params.set('q', query.q);
  return params;
}

export function useCases(query: CaseQuery) {
  return useQuery({
    queryKey: queryKeys.reviewCaseList(query),
    queryFn: ({ signal }) => getJson<CasePageResult>(`/api/review/cases?${listParams(query).toString()}`, signal),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });
}

/** Sections holding cases this account can see, for the queue filter. */
export function useSections() {
  return useQuery({
    queryKey: [...queryKeys.reviewCases, 'sections'],
    queryFn: ({ signal }) => getJson<SectionOption[]>('/api/review/sections', signal),
    staleTime: 5 * 60_000,
  });
}

export function useCase(ticket: string) {
  return useQuery({
    queryKey: queryKeys.reviewCase(ticket),
    queryFn: ({ signal }) => getJson<CaseDetail>(casePath(ticket), signal),
    refetchInterval: 30_000,
  });
}

/** Every case action answers with the fresh case, so the page updates without a second request. */
function useApply(ticket: string) {
  const client = useQueryClient();
  return (detail: CaseDetail) => {
    client.setQueryData(queryKeys.reviewCase(ticket), detail);
    void client.invalidateQueries({ queryKey: queryKeys.reviewCases });
  };
}

export function useAssign(ticket: string) {
  const onSuccess = useApply(ticket);
  return useMutation({ mutationFn: (accountId: string) => sendJson<CaseDetail>(`${casePath(ticket)}/assign`, { account_id: accountId }), onSuccess });
}

export function useAskConsumer(ticket: string) {
  const onSuccess = useApply(ticket);
  return useMutation({
    mutationFn: (body: { kind: RequestKind; note?: string }) => sendJson<CaseDetail>(`${casePath(ticket)}/request`, body),
    onSuccess,
  });
}

/**
 * The engine reprices the bill at the corrected reading. Nothing is saved, so it is safe to cache per reading
 * and to ask again as the AE types. Null reading means nothing to ask yet.
 */
export function usePreview(ticket: string, reading: number | null) {
  return useQuery({
    queryKey: [...queryKeys.reviewCase(ticket), 'preview', reading],
    queryFn: () => sendJson<Preview>(`${casePath(ticket)}/preview`, { corrected_present_reading: reading }),
    enabled: reading !== null,
    staleTime: Infinity,
    retry: false,
  });
}

export function useDecide(ticket: string) {
  const onSuccess = useApply(ticket);
  return useMutation({ mutationFn: (body: NewDecision) => sendJson<CaseDetail>(`${casePath(ticket)}/decisions`, body), onSuccess });
}

type DecisionAction = 'approve' | 'reject' | 'withdraw' | 'applied';

export function useDecisionAction(ticket: string, action: DecisionAction) {
  const onSuccess = useApply(ticket);
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body?: Record<string, string> }) => sendJson<CaseDetail>(`${decisionPath(id)}/${action}`, body),
    onSuccess,
  });
}

/** Each unmask is audited on the server, so it is a deliberate click and never cached. */
export function useUnmask(ticket: string) {
  return useMutation({ mutationFn: () => sendJson<{ service_number: string }>(`${casePath(ticket)}/unmask`) });
}

export function revisionsCsvUrl(range: { from: string; to: string }): string {
  const params = new URLSearchParams();
  if (range.from) params.set('from', range.from);
  if (range.to) params.set('to', range.to);
  const text = params.toString();
  return `/api/review/revisions.csv${text ? `?${text}` : ''}`;
}
