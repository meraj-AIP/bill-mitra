import { AssistCard, type AssistView } from '@/shared/components/AssistCard';
import { describeError } from '@/shared/feedback';
import { revealSection } from '@/shared/lib/reveal';

import { useAskConsumer, useCaseAssist, useDraft, useRefreshCaseAssist, type CaseAssist as Assist } from '../api/reviewApi';
import type { CaseDetail } from '../api/types';
import { OPEN_FOR_DECISION } from '../model/decision';
import { CASE_SECTION } from '../model/labels';

/** The step as a button, only when this account can take it on this case. */
function actionFor(c: CaseDetail, { suggested, why }: Assist, onAsk: () => void): AssistView['action'] {
  if (suggested === 'ask_consumer') return c.can.request_info ? { label: 'Ask the consumer', why, run: onAsk } : null;
  const can = c.can.decide && OPEN_FOR_DECISION.has(c.state);
  return can ? { label: 'Go to the decision', why, run: () => revealSection(CASE_SECTION.decision) } : null;
}

/** The AI read of the case. When the rules already suggest a decision, it adds only the plain summary and the
 * questions: its own list of conflicts and next step would repeat the suggestion, or worse, contradict it. */
export function CaseAssist({ c, onAsk }: { c: CaseDetail; onAsk: () => void }) {
  const assist = useCaseAssist(c.ticket);
  const refresh = useRefreshCaseAssist(c.ticket);
  const ask = useAskConsumer(c.ticket);
  const ruled = Boolean(useDraft(c.ticket, c.can.decide).data);
  const data = assist.data;
  const view: AssistView | null = data ? {
    summary: data.summary,
    lists: ruled ? [] : [{ title: 'Where the facts disagree', items: data.conflicts, empty: 'The engine found nothing that disagrees.' }],
    questions: data.questions,
    action: ruled ? null : actionFor(c, data, onAsk),
    wordedBy: data.worded_by ?? 'rules',
  } : null;
  const failed = assist.error ?? refresh.error;
  return (
    <AssistCard subject="this case" view={view} pending={assist.isFetching || refresh.isPending} error={failed ? describeError(failed, 'AI assist').message : null}
      onAsk={() => refresh.mutate()}
      onSendQuestion={c.can.request_info ? (text) => ask.mutateAsync({ kind: 'note', note: text }) : null} foldQuestions />
  );
}
