import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';

import type { CaseDetail, CasePageResult, CaseQuery, Draft, NewDecision, Preview, RequestKind, SectionOption } from './types';

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
    refetchInterval: 60_000,
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
  return useMutation({ meta: { action: 'Moving the case', success: 'Case moved' }, mutationFn: (accountId: string) => sendJson<CaseDetail>(`${casePath(ticket)}/assign`, { account_id: accountId }), onSuccess });
}

export function useAskConsumer(ticket: string) {
  const onSuccess = useApply(ticket);
  return useMutation({ meta: { action: 'The request', success: 'Request sent to the consumer' },
    mutationFn: (body: { kind: RequestKind; note?: string }) => sendJson<CaseDetail>(`${casePath(ticket)}/request`, body),
    onSuccess,
  });
}

/** The rules' suggested decision, or null when no rule is sure enough. Only asked for by accounts that decide. */
export function useDraft(ticket: string, enabled: boolean) {
  return useQuery({
    queryKey: [...queryKeys.reviewCase(ticket), 'draft'],
    queryFn: ({ signal }) => getJson<Draft | null>(`${casePath(ticket)}/draft`, signal),
    enabled,
    staleTime: 60_000,
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
  return useMutation({ meta: { action: 'Recording the decision', success: 'Decision recorded' }, mutationFn: (body: NewDecision) => sendJson<CaseDetail>(`${casePath(ticket)}/decisions`, body), onSuccess });
}

type DecisionAction = 'approve' | 'reject' | 'withdraw' | 'applied';

const DECISION_SAID: Record<DecisionAction, { action: string; success: string }> = {
  approve: { action: 'The approval', success: 'Decision approved' },
  reject: { action: 'Sending it back', success: 'Decision sent back to the AE' },
  withdraw: { action: 'Withdrawing', success: 'Decision withdrawn' },
  applied: { action: 'Marking it applied', success: 'Marked applied in billing' },
};

export function useDecisionAction(ticket: string, action: DecisionAction) {
  const onSuccess = useApply(ticket);
  return useMutation({ meta: DECISION_SAID[action],
    mutationFn: ({ id, body }: { id: number; body?: Record<string, string> }) => sendJson<CaseDetail>(`${decisionPath(id)}/${action}`, body),
    onSuccess,
  });
}

/** Each unmask is audited on the server, so it is a deliberate click and never cached. */
export function useUnmask(ticket: string) {
  return useMutation({ meta: { action: 'Showing the number' }, mutationFn: () => sendJson<{ service_number: string }>(`${casePath(ticket)}/unmask`) });
}

export function revisionsCsvUrl(range: { from: string; to: string }): string {
  const params = new URLSearchParams();
  if (range.from) params.set('from', range.from);
  if (range.to) params.set('to', range.to);
  const text = params.toString();
  return `/api/review/revisions.csv${text ? `?${text}` : ''}`;
}

/** Contract section 2. The drafted decision stays the rules' job; this only reads the case and suggests a step. */
export interface CaseAssist {
  summary: string;
  /** From the engine facts: spike, misread signal, estimated reading, charges mismatch. */
  conflicts: string[];
  questions: Array<{ text: string; why: string }>;
  suggested: 'draft' | 'ask_consumer' | 'decide';
  /** One English line on why that step. */
  why: string;
  /** Not in the contract for cases yet; read as rules when missing. */
  worded_by?: 'ai' | 'rules';
}

/** The case's stored brief, shared by everyone who opens it; the server writes it again only when the case moves on. */
export function useCaseAssist(ticket: string) {
  return useQuery({
    queryKey: ['review', 'case', ticket, 'assist'],
    queryFn: ({ signal }) => getJson<CaseAssist>(`${casePath(ticket)}/assist`, signal),
    staleTime: 60_000,
    retry: false,
  });
}

/** Refresh: a new brief written now, which then becomes the shared one. */
export function useRefreshCaseAssist(ticket: string) {
  const client = useQueryClient();
  return useMutation({ meta: { action: 'AI assist' },
    mutationFn: () => sendJson<CaseAssist>(`${casePath(ticket)}/assist`),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['review', 'case', ticket, 'assist'] }),
  });
}
