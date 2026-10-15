import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ComplaintDetail, ComplaintStatus, Triage } from '@/features/complaints';
import { getJson, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';

import { useApplyDetail } from './consoleApi';

const path = (ticket: string) => `/api/console/complaints/${encodeURIComponent(ticket)}`;

export interface Suggestion {
  /** Null when the bill behind the complaint is no longer stored. */
  text: string | null;
  triage: Triage | null;
  /** 'ai' when the model reworded the checked draft and the number guard passed it. */
  worded_by: 'ai' | 'rules' | null;
  quick: string[];
}

export type InfoKind = 'meter_photo' | 'bill_photo' | 'details';

export function useSuggestion(ticket: string, enabled: boolean) {
  return useQuery({
    queryKey: [...queryKeys.consoleComplaint(ticket), 'suggestion'],
    queryFn: ({ signal }) => getJson<Suggestion>(`${path(ticket)}/suggestion`, signal),
    enabled,
    staleTime: Infinity,
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
