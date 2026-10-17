import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ComplaintDetail, ComplaintRow, ComplaintStatus, Priority, Source, Triage } from '@/features/complaints';
import { getJson, isStatus, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import type { Discom, Page } from '@/shared/api/types';

import type { InfoKind } from './actionsApi';

export interface Summary {
  days: number;
  discom: string | null;
  bills_read: number;
  /** complaints and overcharge_flagged cover the selected window only. */
  complaints: number;
  overcharge_flagged: number;
  questions: number;
  alerts: number;
  audit: Record<string, number>;
  languages: Array<{ language: string; count: number }>;
  intents: Array<{ intent: string; count: number }>;
  daily: Array<{ date: string; bills: number; questions: number }>;
  sections: Array<{ section: string; bills: number; mismatches: number; avg_units: number }>;
  reads: {
    total: number; trusted_first_time: number; reread_rescued: number; retake: number; not_a_bill: number; failed: number;
    median_ms: number | null; p90_ms: number | null;
  };
  explanations: { llm_pass: number; llm_fallback: number; template: number };
  complaints_by_status: Partial<Record<ComplaintStatus, number>>;
  complaints_overdue: number;
  /** Days a consumer is told to expect a reply; past this a complaint is overdue. */
  reply_days: number;
  week: { this_week: WeekCounts; last_week: WeekCounts; failed_deliveries: number };
}

export interface WeekCounts { bills: number; mismatches: number; opened: number; closed: number }

export const SUMMARY_DAYS = [7, 30, 90, 365] as const;
export interface SummaryFilters {
  days: (typeof SUMMARY_DAYS)[number];
  discom: Discom | '';
}

/** Staff only: the endpoint answers 401 to anyone else, which signs the visitor out, so callers gate it. */
export function useSummary(enabled = true, filters: SummaryFilters = { days: 30, discom: '' }) {
  const params = new URLSearchParams({ days: String(filters.days) });
  if (filters.discom) params.set('discom', filters.discom);
  return useQuery({
    queryKey: [...queryKeys.consoleSummary, filters],
    enabled,
    queryFn: ({ signal }) => getJson<Summary>(`/api/console/summary?${params.toString()}`, signal),
    placeholderData: keepPreviousData,
    refetchInterval: 15_000,
  });
}

/** Same filters as the inbox list; a plain link works because the cookie is same-origin. */
export function exportUrl(query: InboxQuery): string {
  // The CSV keeps date order; priority only matters on screen.
  const params = new URLSearchParams({ sort: query.sort === 'oldest' ? 'oldest' : 'newest' });
  if (query.status) params.set('status', query.status);
  if (query.discom) params.set('discom', query.discom);
  if (query.q) params.set('q', query.q);
  addCatalogue(params, query);
  return `/api/console/complaints.csv?${params.toString()}`;
}

export interface InboxQuery {
  page: number;
  pageSize: number;
  status: ComplaintStatus | '';
  discom: Discom | '';
  q: string;
  sort: 'priority' | 'newest' | 'oldest';
  triage: Triage | '';
  failed: boolean;
  type: string;
  priority: Priority | '';
  source: Source | '';
  /** Held by the signed-in account. */
  withMe: boolean;
  /** Held by the signed-in account and waiting on staff, not on the consumer. */
  waitingOnMe: boolean;
}

function addCatalogue(params: URLSearchParams, query: InboxQuery) {
  if (query.withMe) params.set('with_me', 'true');
  if (query.waitingOnMe) params.set('waiting_on_me', 'true');
  if (query.type) params.set('type', query.type);
  if (query.priority) params.set('priority', query.priority);
  if (query.source) params.set('source', query.source);
}

export function useInbox(query: InboxQuery) {
  const params = new URLSearchParams({ page: String(query.page), page_size: String(query.pageSize), sort: query.sort });
  if (query.status) params.set('status', query.status);
  if (query.triage) params.set('triage', query.triage);
  if (query.failed) params.set('failed', 'true');
  if (query.discom) params.set('discom', query.discom);
  if (query.q) params.set('q', query.q);
  addCatalogue(params, query);
  return useQuery({
    queryKey: queryKeys.consoleComplaintList(query),
    queryFn: ({ signal }) => getJson<Page<ComplaintRow>>(`/api/console/complaints?${params.toString()}`, signal),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });
}

const path = (ticket: string) => `/api/console/complaints/${encodeURIComponent(ticket)}`;

export function useConsoleComplaint(ticket: string) {
  return useQuery({
    queryKey: queryKeys.consoleComplaint(ticket),
    queryFn: ({ signal }) => getJson<ComplaintDetail>(path(ticket), signal),
    refetchInterval: 20_000,
    retry: (count, error) => count < 1 && !isStatus(error, 404),
  });
}

export function useApplyDetail(ticket: string) {
  const client = useQueryClient();
  return (detail: ComplaintDetail) => {
    client.setQueryData(queryKeys.consoleComplaint(ticket), detail);
    // What fits the complaint moves with the thread: an answered ask, a new status.
    void client.invalidateQueries({ queryKey: [...queryKeys.consoleComplaint(ticket), 'options'] });
    void client.invalidateQueries({ queryKey: [...queryKeys.consoleComplaints, 'list'] });
    void client.invalidateQueries({ queryKey: queryKeys.consoleSummary });
  };
}

export function useReply(ticket: string) {
  const apply = useApplyDetail(ticket);
  return useMutation({
    mutationFn: (body: { body: string; status?: ComplaintStatus; asks?: InfoKind }) => sendJson<ComplaintDetail>(`${path(ticket)}/reply`, body),
    onSuccess: apply,
  });
}

export function useSetStatus(ticket: string) {
  const apply = useApplyDetail(ticket);
  return useMutation({
    mutationFn: (status: ComplaintStatus) => sendJson<ComplaintDetail>(`${path(ticket)}/status`, { status }),
    onSuccess: apply,
  });
}
