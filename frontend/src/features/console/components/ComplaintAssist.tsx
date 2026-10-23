import { useAuth } from '@/features/auth';
import { COMPLAINT_STATUSES, type ComplaintDetail, type ComplaintStatus } from '@/features/complaints';
import { AssistCard, type AssistView } from '@/shared/components/AssistCard';

import { useAskQuestion, useReplyOptions, type ReplyOptions } from '../api/actionsApi';
import { useComplaintAssist, useRefreshAssist, type ComplaintAssist as Assist, type NextAction } from '../api/assistApi';
import { useSetStatus } from '../api/consoleApi';
import { reveal, type FocusTarget } from '../model/focus';
import { describeError, useConfirm } from '@/shared/feedback';

const norm = (s: string) => s.trim().toLowerCase().replace(/[\s-]+/g, '_');
const statusFor = (key: string): ComplaintStatus | undefined => COMPLAINT_STATUSES.find((s) => norm(s) === norm(key));
const isOpen = (c: ComplaintDetail) => c.status === 'Open' || c.status === 'In progress';

interface Step { label: string; target: FocusTarget; status?: ComplaintStatus }

function statusStep(key: string, complaint: ComplaintDetail): Step | null {
  // A reading check's status follows its case decision, so the assist never offers to set it.
  if (complaint.kind === 'wrong_reading') return null;
  const status = statusFor(key);
  return status && status !== complaint.status ? { label: `Set status to ${status}`, target: 'status', status } : null;
}

/** The button for a suggestion, or null when the rules no longer offer it (the server drops unknown keys too). */
function stepFor(action: NextAction, options: ReplyOptions | undefined, complaint: ComplaintDetail): Step | null {
  if (action.kind === 'status') return statusStep(action.key, complaint);
  if (action.kind === 'assign') return complaint.assignable?.length ? { label: 'Open hand over', target: 'handoff' } : null;
  if (action.kind === 'request') {
    const r = options?.requests.find((x) => x.kind === action.key);
    return r ? { label: `Ask for: ${r.label}`, target: 'request' } : null;
  }
  const o = options?.options.find((x) => x.key === action.key);
  return o ? { label: `Load the reply: ${o.label}`, target: 'reply' } : null;
}

function toView(data: Assist, action: AssistView['action']): AssistView {
  return {
    summary: data.summary,
    lists: [{ title: 'Still missing', items: data.missing, empty: 'Nothing obvious is missing.' }],
    questions: data.questions,
    action,
    wordedBy: data.worded_by,
  };
}

interface Props {
  complaint: ComplaintDetail;
  /** Opens a part of the actions column with the suggestion already chosen. */
  onFocus: (target: FocusTarget, key: string) => void;
}

/** The suggested step as a button: it loads, opens or sets what the suggestion names. */
export function useNextStep(complaint: ComplaintDetail, next: NextAction | null, canReply: boolean, onFocus: Props['onFocus']): AssistView['action'] {
  const options = useReplyOptions(complaint.ticket);
  const setStatus = useSetStatus(complaint.ticket);
  const confirm = useConfirm();
  // Hand over has its own check on the server; the other steps need the reply permission.
  const step = next && (canReply || next.kind === 'assign') ? stepFor(next, options.data, complaint) : null;
  if (!step || !next) return null;
  const run = async () => {
    if (step.status) {
      if (await confirm({ title: `Set the complaint to ${step.status}?`, confirmLabel: `Set to ${step.status}`,
        tone: step.status === 'Resolved' || step.status === 'Rejected' ? 'warning' : 'default',
        body: 'The consumer gets a short message about it.' })) {
        setStatus.mutate(step.status, { onSuccess: () => reveal('status') });
      }
      return;
    }
    // A hand over opens with the suggested person picked; its key is only the action's name.
    onFocus(step.target, step.target === 'handoff' ? next.account_id ?? '' : next.key);
    reveal(step.target);
  };
  return { label: step.label, why: next.why, run: () => void run(), pending: setStatus.isPending, error: null };
}

export function ComplaintAssist({ complaint, onFocus }: Props) {
  const { can } = useAuth();
  const assist = useComplaintAssist(complaint, true);
  const refresh = useRefreshAssist(complaint.ticket);
  const question = useAskQuestion(complaint.ticket);
  const canReply = can('complaints.reply');
  const action = useNextStep(complaint, assist.data?.next_action ?? null, canReply, onFocus);
  return (
    <AssistCard subject="this complaint" view={assist.data ? toView(assist.data, action) : null} pending={assist.isFetching || refresh.isPending}
      error={assistError(assist.error ?? refresh.error)} onAsk={() => refresh.mutate()}
      onSendQuestion={canReply && isOpen(complaint) ? (text) => question.mutateAsync(text) : null} />
  );
}

function assistError(error: Error | null): string | null {
  return error ? describeError(error, 'AI assist').message : null;
}
