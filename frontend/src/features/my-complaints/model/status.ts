import type { MyStatus } from '../api/types';

export const MY_STATUS: Record<MyStatus, { label: string; tone: 'default' | 'info' | 'warning' | 'success'; hint: string }> = {
  received: { label: 'Received', tone: 'default', hint: 'We have your complaint and will look at it soon.' },
  in_progress: { label: 'In progress', tone: 'info', hint: 'We are looking into it.' },
  waiting_for_you: { label: 'Waiting for you', tone: 'warning', hint: 'We asked you something. Please reply below.' },
  resolved: { label: 'Resolved', tone: 'success', hint: 'We have answered your complaint.' },
  closed: { label: 'Closed', tone: 'default', hint: 'This complaint is closed.' },
};

/** The steps a complaint walks through. Closed sits on the last step, like resolved. */
export const STEPS: MyStatus[] = ['received', 'in_progress', 'waiting_for_you', 'resolved'];

export function stepIndex(status: MyStatus): number {
  return status === 'closed' ? STEPS.length - 1 : STEPS.indexOf(status);
}

/** Our wording for a known code; a code a newer server adds shows with the server's own label. */
export function statusOf(code: string, serverLabel: string) {
  return MY_STATUS[code as MyStatus] ?? { label: serverLabel, tone: 'default' as const, hint: '' };
}
