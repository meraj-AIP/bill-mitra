import { useMutation } from '@tanstack/react-query';

import { sendJson } from '@/shared/api/http';

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
}

/** On demand only: a press of Ask AI, never on page load. */
export function useComplaintAssist(ticket: string) {
  return useMutation({
    mutationFn: () => sendJson<ComplaintAssist>(`/api/console/complaints/${encodeURIComponent(ticket)}/assist`),
  });
}
