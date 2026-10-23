import type { CaseDetail } from '../api/types';

/** What the case waits on, for someone with nothing to do on it right now. */
export function waitingOn(c: CaseDetail): string {
  if (c.state === 'info_requested') return 'The consumer has been asked for more. The section AE decides once it is in, or on what is on file.';
  if (c.state === 'awaiting_review' || c.state === 'rejected') return 'Waiting for the section AE to decide. You can follow it here.';
  if (c.state === 'awaiting_approval') return 'A decision is waiting for a billing approver. Nothing to do here until they act.';
  if (c.state === 'decided') return 'Decided. Any revision now waits to be entered in the DISCOM billing system.';
  return 'Closed. The revision is in the official bill and the consumer has been told.';
}

/** A line above the decision when the state changes what the AE should read first. */
export function decideHint(c: CaseDetail): string | null {
  if (c.state === 'rejected') return 'The approver sent the last decision back. Read their note in Decisions, then decide again.';
  if (c.state === 'info_requested') return 'The consumer has been asked for more. You can still decide on what is on file.';
  return null;
}
