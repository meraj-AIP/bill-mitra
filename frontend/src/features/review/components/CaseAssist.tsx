import { AssistCard, type AssistView } from '@/shared/components/AssistCard';
import { revealSection } from '@/shared/lib/reveal';

import { useAskConsumer, useCaseAssist, type CaseAssist as Assist } from '../api/reviewApi';
import type { CaseDetail } from '../api/types';
import { OPEN_FOR_DECISION } from '../model/decision';
import { CASE_SECTION } from '../model/labels';

const STEP: Record<Assist['suggested'], { label: string; section: string }> = {
  draft: { label: 'Go to the suggested decision', section: CASE_SECTION.decision },
  decide: { label: 'Go to the decision', section: CASE_SECTION.decision },
  ask_consumer: { label: 'Ask the consumer', section: CASE_SECTION.ask },
};

/** The step as a button, only when this account can take it on this case. */
function actionFor(c: CaseDetail, { suggested, why }: Assist): AssistView['action'] {
  const step = STEP[suggested];
  const can = suggested === 'ask_consumer' ? c.can.request_info : c.can.decide && OPEN_FOR_DECISION.has(c.state);
  return can ? { label: step.label, why, run: () => revealSection(step.section) } : null;
}

export function CaseAssist({ c }: { c: CaseDetail }) {
  const assist = useCaseAssist(c.ticket);
  const ask = useAskConsumer(c.ticket);
  const data = assist.data;
  const view: AssistView | null = data ? {
    summary: data.summary,
    lists: [{ title: 'Where the facts disagree', items: data.conflicts, empty: 'The engine found nothing that disagrees.' }],
    questions: data.questions,
    action: actionFor(c, data),
    wordedBy: data.worded_by ?? 'rules',
  } : null;
  return (
    <AssistCard subject="this case" view={view} pending={assist.isPending} error={assist.error?.message ?? null}
      onAsk={() => assist.mutate()}
      onSendQuestion={c.can.request_info ? (text) => ask.mutateAsync({ kind: 'note', note: text }) : null} />
  );
}
