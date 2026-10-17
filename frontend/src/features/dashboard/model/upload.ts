import { NetworkError } from '@/shared/api/http';
import { errorText, isTransient } from '@/shared/api/retry';

const LOST = 'The connection dropped while your bill was being read. If it went through, it will appear in My bills below.';

/** A lost answer may mean the bill was saved, so it points to My bills rather than inviting a second read. */
export function uploadErrorText(error: Error): string {
  return error instanceof NetworkError && error.sent ? LOST : errorText(error);
}

/** Resending the same photo is offered only when the first one surely was not read. */
export function canResend(error: Error): boolean {
  return isTransient(error) && !(error instanceof NetworkError && error.sent);
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

/** The error worth showing: a bad pick first, then the send, then a queued read that failed for good. */
export function uploadProblem(picked: string | null, failure: Error | null, jobFailed: string | null): string | null {
  return picked ?? (failure ? uploadErrorText(failure) : null) ?? jobFailed;
}
