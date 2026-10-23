import { NetworkError } from '@/shared/api/http';
import { isTransient } from '@/shared/api/retry';

import type { BillReport, ExtractJob, Outcome } from '../api/types';

export const LOST_UPLOAD = 'The connection dropped while your bill was being read. If it went through, it will appear in My bills below.';

/** A lost answer may mean the bill was saved, so it points to My bills rather than inviting a second read. */
export const isLostUpload = (error: Error) => error instanceof NetworkError && error.sent;

/** Resending the same photo is offered only when the first one surely was not read. */
export function canResend(error: Error): boolean {
  return isTransient(error) && !isLostUpload(error);
}

function unsavedReport(outcome: Outcome, reason: string | null): BillReport {
  return { id: null, created_at: null, media_url: null, mime_type: 'image/jpeg', outcome, outcome_reason: reason,
    classification: null, bill: null, capture: null, analysis: null };
}

/**
 * How a queued read ended when there is no saved bill to open: a retake, not a bill, or a read that failed for good.
 * Older servers answer done with no bill_id and the reason in detail; newer ones name the outcome.
 */
export function jobEnding(job: ExtractJob | undefined): BillReport | null {
  if (!job) return null;
  const reason = job.reason ?? job.detail ?? null;
  // A read that failed for good is not the photo's fault, so the failed view never asks for a better one.
  if (job.status === 'failed') return unsavedReport('reading_failed', reason);
  if (job.status === 'done' && !job.bill_id) return unsavedReport(job.outcome ?? 'retake', reason);
  return null;
}

/** What the dashboard shows in place of the upload card. */
export type UploadView = 'upload' | 'reading' | 'waiting' | 'failed' | 'unsaved';

interface ViewInput { pending: boolean; waiting: boolean; unsaved: boolean; failedWithPhoto: boolean }

export function viewOf({ pending, waiting, unsaved, failedWithPhoto }: ViewInput): UploadView {
  if (pending) return 'reading';
  if (waiting) return 'waiting';
  if (unsaved) return 'unsaved';
  return failedWithPhoto ? 'failed' : 'upload';
}
