import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ComplaintDetail, ComplaintStatus, Triage } from '@/features/complaints';
import { getJson, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import { IDEMPOTENT } from '@/shared/api/retry';

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
  return useMutation({ meta: { action: 'Rewording the reply' },
    ...IDEMPOTENT,
    mutationFn: (optionKey: string) => sendJson<Draft>(`${path(ticket)}/draft`, { option_key: optionKey }),
  });
}

export function useRequestInfo(ticket: string) {
  const apply = useApplyDetail(ticket);
  return useMutation({ meta: { action: 'The request', success: 'Request sent to the consumer' },
    mutationFn: (kind: InfoKind) => sendJson<ComplaintDetail>(`${path(ticket)}/request`, { kind }),
    onSuccess: apply,
  });
}

export function useRetry(ticket: string) {
  const apply = useApplyDetail(ticket);
  return useMutation({ meta: { action: 'Sending it again', success: 'Sent again' },
    mutationFn: (messageId: number) => sendJson<ComplaintDetail>(`${path(ticket)}/messages/${messageId}/retry`),
    onSuccess: apply,
  });
}

/** Hand-off contract section 4: every hand over carries a note of 10 to 300 characters. */
export const HANDOFF_NOTE = { min: 10, max: 300 } as const;

export function useAssign(ticket: string) {
  const apply = useApplyDetail(ticket);
  return useMutation({ meta: { action: 'The hand over', success: 'Handed over' },
    mutationFn: (body: { account_id: string; note: string }) => sendJson<ComplaintDetail>(`${path(ticket)}/assign`, body),
    onSuccess: apply,
  });
}

/** Returns the complaint to whoever handed it over, with a note. */
export function useSendBack(ticket: string) {
  const apply = useApplyDetail(ticket);
  return useMutation({ meta: { action: 'Sending it back', success: 'Sent back' },
    mutationFn: (note: string) => sendJson<ComplaintDetail>(`${path(ticket)}/return`, { note }),
    onSuccess: apply,
  });
}

/** A question in the consumer's language, sent as a request of kind note so their answer is filed under it. */
export function useAskQuestion(ticket: string) {
  const apply = useApplyDetail(ticket);
  return useMutation({ meta: { action: 'The question', success: 'Question sent to the consumer' },
    mutationFn: (note: string) => sendJson<ComplaintDetail>(`${path(ticket)}/request`, { kind: 'note', note }),
    onSuccess: apply,
  });
}

export interface BulkResult { done: string[]; skipped: Array<{ ticket: string; reason: string }> }

export function useBulk() {
  const client = useQueryClient();
  return useMutation({ meta: { action: 'The bulk action' },
    mutationFn: (body: { tickets: string[]; status?: ComplaintStatus; send_explanation: boolean }) =>
      sendJson<BulkResult>('/api/console/complaints/bulk', body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.consoleComplaints });
      void client.invalidateQueries({ queryKey: queryKeys.consoleSummary });
    },
  });
}
