import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, sendJson } from '@/shared/api/http';

/** Contract section 2. `key` is one of the options or requests the rules already offer for this complaint. */
export interface NextAction {
  kind: 'reply_option' | 'request' | 'status' | 'assign';
  key: string;
  why: string;
  /** For assign: the person the rules would hand it to, when this viewer may. */
  account_id?: string | null;
}

export interface ComplaintAssist {
  /** Two or three English lines for staff. */
  summary: string;
  missing: string[];
  /** At most three, in the consumer's language. */
  questions: Array<{ text: string; why: string }>;
  next_action: NextAction | null;
  worded_by: 'ai' | 'rules';
  /** When the stored brief was written. One brief per complaint, shared by everyone who opens it. */
  generated_at?: string;
}

const assistUrl = (ticket: string) => `/api/console/complaints/${encodeURIComponent(ticket)}/assist`;
const assistKey = (ticket: string) => ['console', 'complaints', 'one', ticket, 'assist'] as const;

/**
 * The stored brief for this complaint. The server writes it once and again only when the complaint moves on, so
 * opening a complaint never costs a new model call by itself. Status and message count in the key fetch it again then.
 */
export function useComplaintAssist(complaint: { ticket: string; status: string; messages: unknown[] }, enabled: boolean) {
  return useQuery({
    queryKey: [...assistKey(complaint.ticket), complaint.status, complaint.messages.length],
    queryFn: ({ signal }) => getJson<ComplaintAssist>(assistUrl(complaint.ticket), signal),
    enabled,
    staleTime: 60_000,
    retry: false,
  });
}

/** Refresh: a new brief written now, which then becomes the shared one. */
export function useRefreshAssist(ticket: string) {
  const client = useQueryClient();
  return useMutation({ meta: { action: 'The AI brief' },
    mutationFn: () => sendJson<ComplaintAssist>(assistUrl(ticket)),
    onSuccess: () => void client.invalidateQueries({ queryKey: assistKey(ticket) }),
  });
}
