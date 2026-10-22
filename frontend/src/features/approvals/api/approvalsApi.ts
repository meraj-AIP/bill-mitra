import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import type { Page } from '@/shared/api/types';

export const PROPOSAL_KINDS = ['explain_correct', 'request_bill', 'request_meter', 'decide_correct'] as const;
export type ProposalKind = (typeof PROPOSAL_KINDS)[number];
export const PROPOSAL_STATES = ['pending', 'approved', 'rejected', 'stale'] as const;
export type ProposalState = (typeof PROPOSAL_STATES)[number];

/** A routine action the rules prepared. Nothing is sent or decided until an officer approves it. */
export interface Proposal {
  id: number;
  ticket: string;
  kind: ProposalKind;
  why: string[];
  state: ProposalState;
  created_at: string;
  decided_by_name: string | null;
  decided_at: string | null;
  note: string | null;
  complaint_type: string | null;
  type_label: string | null;
  complaint_kind: string;
  discom: string | null;
  section: string | null;
  bill_month: string | null;
  complaint_created_at: string;
}

export interface ProposalPage extends Page<Proposal> {
  /** Waiting proposals the viewer may approve, by kind. Filters do not narrow it. */
  counts: Partial<Record<ProposalKind, number>>;
}

export interface ApprovalsQuery {
  page: number;
  pageSize: number;
  kind: ProposalKind | '';
  state: ProposalState | '';
}

export interface BatchResult {
  done: number[];
  skipped: { id: number; reason: string }[];
}

const BASE = '/api/console/proposals';

export function useProposals(query: ApprovalsQuery) {
  const params = new URLSearchParams({ page: String(query.page), page_size: String(query.pageSize) });
  if (query.kind) params.set('kind', query.kind);
  if (query.state) params.set('state', query.state);
  return useQuery({
    queryKey: queryKeys.approvalList(query),
    queryFn: ({ signal }) => getJson<ProposalPage>(`${BASE}?${params.toString()}`, signal),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });
}

/** How many proposals wait for this account, for the badge on the tab. */
export function usePendingApprovals(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.approvalCount,
    queryFn: ({ signal }) => getJson<{ pending: number }>(`${BASE}/count`, signal),
    enabled,
    refetchInterval: 120_000,
  });
}

function useRefresh() {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: queryKeys.approvals });
    void client.invalidateQueries({ queryKey: queryKeys.consoleComplaints });
    void client.invalidateQueries({ queryKey: queryKeys.reviewCases });
  };
}

/** Approving carries the action out, so it is never repeated on its own after a lost answer. */
export function useApprove() {
  const onSuccess = useRefresh();
  return useMutation({ meta: { action: 'The approval' }, mutationFn: (id: number) => sendJson<Proposal>(`${BASE}/${id}/approve`), onSuccess });
}

export function useApproveMany() {
  const onSuccess = useRefresh();
  return useMutation({ meta: { action: 'Approving the selection' }, mutationFn: (ids: number[]) => sendJson<BatchResult>(`${BASE}/approve`, { ids }), onSuccess });
}

export function useReject() {
  const onSuccess = useRefresh();
  return useMutation({ meta: { action: 'The rejection', success: 'Proposal rejected' }, mutationFn: ({ id, note }: { id: number; note: string }) => sendJson<Proposal>(`${BASE}/${id}/reject`, note ? { note } : {}),
    onSuccess });
}
