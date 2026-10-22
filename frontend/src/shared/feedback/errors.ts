import { ApiError, NetworkError } from '@/shared/api/http';

export interface Described {
  title: string;
  message: string;
  severity: 'error' | 'warning';
  /** Trying the same thing again may work: the server faulted or the request never left the browser. */
  retry: boolean;
  /** What is on screen may be out of date (someone else acted, or an answer was lost), so reload it. */
  refresh: boolean;
}

type Rule = Omit<Described, 'message'> & { fallback: string; keepServerText: boolean };
const rule = (title: string, severity: Described['severity'], fallback: string, flags: Partial<Rule> = {}): Rule =>
  ({ title, severity, fallback, retry: false, refresh: false, keepServerText: true, ...flags });

// What each answer means for the person, and whether the server's own sentence is worth showing.
const BY_STATUS: Record<number, Rule> = {
  400: rule('Check the details', 'error', 'Something in the form is not accepted. Check it and try again.'),
  401: rule('Signed out', 'warning', 'Your session ended. Sign in again to carry on.', { keepServerText: false }),
  403: rule('Not allowed', 'error', 'Your role cannot do this. Ask an admin if you need it.'),
  404: rule('No longer here', 'warning', 'It may have been moved, closed or removed. The page is refreshed.', { refresh: true }),
  409: rule('Already changed', 'warning', 'Someone else acted on this first. The page is refreshed with the latest.', { refresh: true }),
  413: rule('File too large', 'error', 'Choose a smaller file and try again.'),
  422: rule('Check the details', 'error', 'Something in the form is not accepted. Check it and try again.'),
  429: rule('Too many attempts', 'warning', 'Wait a minute, then try again.'),
};

const LOST: Described = { title: 'No answer from the server', severity: 'warning', retry: false, refresh: true,
  message: 'The connection dropped before we heard back, so it may have gone through. The page is refreshed; check it before trying again.' };
const OFFLINE: Described = { title: 'You are offline', severity: 'warning', retry: true, refresh: false,
  message: 'Nothing was sent. Check your connection and try again.' };

/** What went wrong and what to do now, in plain words, for any failed request. The server's own sentence is kept
 * where it says something specific (a 4xx detail), and replaced where it would only confuse. */
export function describeError(error: unknown, action = 'That'): Described {
  if (error instanceof NetworkError) return error.sent ? LOST : OFFLINE;
  const code = error instanceof ApiError ? error.status : 0;
  const detail = error instanceof Error && !/^Request failed/.test(error.message) ? error.message : '';
  if (code >= 500) {
    return { title: `${action} did not go through`, severity: 'error', retry: true, refresh: false,
      message: 'Something went wrong on our side. Nothing was changed. Try again in a moment.' };
  }
  const found = BY_STATUS[code];
  if (!found) return { title: `${action} did not go through`, severity: 'error', retry: false, refresh: false, message: detail || 'Please try again.' };
  return withMessage(found, detail);
}

function withMessage({ fallback, keepServerText, ...said }: Rule, detail: string): Described {
  if (!keepServerText || !detail) return { ...said, message: fallback };
  return { ...said, message: said.refresh ? `${detail} The page is refreshed with the latest.` : detail };
}
