import { ApiError, NetworkError } from './http';

/** Three retries after the first try, matching the backend's attempt counts. */
const MAX_RETRIES = 3;

/** A network drop or a server fault may clear on its own. A 4xx will not change, so it is never retried. */
export function isTransient(error: unknown): boolean {
  return error instanceof NetworkError || (error instanceof ApiError && error.status >= 500);
}

/** True when the request never fully left the browser, so sending it again cannot repeat an action. */
export function neverSent(error: unknown): boolean {
  return error instanceof NetworkError && !error.sent;
}

/** Exponential backoff with full jitter: up to 1 s, 2 s, 4 s, capped at 8 s. */
export function retryDelay(attempt: number): number {
  return Math.random() * Math.min(8_000, 1_000 * 2 ** attempt);
}

export const retryQuery = (count: number, error: Error): boolean => count < MAX_RETRIES && isTransient(error);

/** The default for every mutation: a reply, decision, hand over or status change is never sent twice. */
export const retryUnsent = (count: number, error: Error): boolean => count < MAX_RETRIES && neverSent(error);

/** Spread into useMutation for routes where a second call changes nothing (a PUT, a mark as read, a draft). */
export const IDEMPOTENT = { retry: retryQuery, retryDelay } as const;

/** Words for a failed action, so a person knows whether to try again or check first. */
export function errorText(error: Error): string {
  if (error instanceof NetworkError) {
    return error.sent
      ? 'The connection dropped before we heard back, so this may have gone through. Check before trying again.'
      : 'Could not reach the server. Check your connection and try again.';
  }
  if (error instanceof ApiError && error.status >= 500) return 'Something went wrong on our side. Please try again in a moment.';
  return error.message;
}
