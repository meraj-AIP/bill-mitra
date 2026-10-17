import { revealSection } from '@/shared/lib/reveal';

/** A part of the actions column the assist card can open with a choice already made. */
export type FocusTarget = 'reply' | 'request' | 'status' | 'handoff';

/** `n` grows on every press, so pressing the same suggestion twice still applies it. */
export interface Focus { target: FocusTarget; key: string; n: number }

export const SECTION_ID: Record<FocusTarget, string> = {
  reply: 'complaint-reply',
  request: 'complaint-request',
  status: 'complaint-status',
  handoff: 'complaint-handoff',
};

export function reveal(target: FocusTarget): void {
  revealSection(SECTION_ID[target]);
}
