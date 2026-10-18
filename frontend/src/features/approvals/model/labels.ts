import type { ProposalKind, ProposalState } from '../api/approvalsApi';

export const KIND_LABEL: Record<ProposalKind, string> = {
  explain_correct: 'Send the checked explanation',
  request_bill: 'Ask for the bill',
  request_meter: 'Ask for a meter photo',
  decide_correct: 'Record the bill as correct',
};

/** What approving does, said before the officer clicks. */
export const KIND_ACTION: Record<ProposalKind, string> = {
  explain_correct: 'Approving sends the checked explanation to the consumer and resolves the complaint.',
  request_bill: 'Approving asks the consumer for a photo of the bill. The complaint stays open.',
  request_meter: 'Approving asks the consumer for a photo of the meter. The complaint stays open.',
  decide_correct: 'Approving records "bill correct" in your name, tells the consumer and closes the case.',
};

export const STATE_LABEL: Record<ProposalState, string> = {
  pending: 'Waiting',
  approved: 'Approved',
  rejected: 'Rejected',
  stale: 'Not carried out',
};

export const KIND_COLOR: Record<ProposalKind, 'primary' | 'info' | 'secondary'> = {
  explain_correct: 'primary',
  request_bill: 'info',
  request_meter: 'info',
  decide_correct: 'secondary',
};

export const APPROVALS_PATH = '/approvals';
