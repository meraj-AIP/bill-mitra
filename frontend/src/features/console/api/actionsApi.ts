import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ComplaintDetail, ComplaintStatus, Triage } from '@/features/complaints';
import { getJson, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';

import { useApplyDetail } from './consoleApi';

const path = (ticket: string) => `/api/console/complaints/${encodeURIComponent(ticket)}`;

export type InfoKind = 'meter_photo' | 'bill_photo' | 'details' | 'earlier_bills' | 'payment_proof';

/** A reply that fits this complaint. `text` is in the consumer's language; label and why are for staff. */
export interface ReplyOption {
  key: string;
  label: string;
  text: string;
  why: string;
  /** Sending this reply also waits for the consumer's answer, like a request. */
  asks: InfoKind | null;
}

export interface RequestOption { kind: InfoKind; label: string; text: string; why: string }

export interface ReplyOptions {
  triage: Triage | null;
  options: ReplyOption[];
  requests: RequestOption[];
}

/** 'rules': the template as built from the complaint. 'ai': reworded by the model, every number checked. */
export interface Draft { text: string; worded_by: 'ai' | 'rules' }

/** Rules only, so it is cheap to load with the page. Refetched with the complaint after every change. */
export function useReplyOptions(ticket: string) {
  return useQuery({
    queryKey: [...queryKeys.consoleComplaint(ticket), 'options'],
    queryFn: ({ signal }) => getJson<ReplyOptions>(`${path(ticket)}/options`, signal),
  });
}

export function useDraftOption(ticket: string) {
  return useMutation({
    mutationFn: (optionKey: string) => sendJson<Draft>(`${path(ticket)}/draft`, { option_key: optionKey }),
  });
}

export function useRequestInfo(ticket: string) {
  const apply = useApplyDetail(ticket);
  return useMutation({
    mutationFn: (kind: InfoKind) => sendJson<ComplaintDetail>(`${path(ticket)}/request`, { kind }),
    onSuccess: apply,
  });
}

export function useRetry(ticket: string) {
  const apply = useApplyDetail(ticket);
  return useMutation({
    mutationFn: (messageId: number) => sendJson<ComplaintDetail>(`${path(ticket)}/messages/${messageId}/retry`),
    onSuccess: apply,
  });
}

/** Contract section 6 lists assign among the actions; the route mirrors the review case one. */
export function useAssign(ticket: string) {
  const apply = useApplyDetail(ticket);
  return useMutation({
    mutationFn: (accountId: string) => sendJson<ComplaintDetail>(`${path(ticket)}/assign`, { account_id: accountId }),
    onSuccess: apply,
  });
}

export interface BulkResult { done: string[]; skipped: Array<{ ticket: string; reason: string }> }

export function useBulk() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { tickets: string[]; status?: ComplaintStatus; send_explanation: boolean }) =>
      sendJson<BulkResult>('/api/console/complaints/bulk', body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.consoleComplaints });
      void client.invalidateQueries({ queryKey: queryKeys.consoleSummary });
    },
  });
}
