import { ApiError, NetworkError } from '@/shared/api/http';

export interface Described {
  title: string;
  message: string;
  severity: 'error' | 'warning';
  /** Trying the same thing again may work: the server faulted or the request never left the browser. */
  retry: boolean;
  /** What is on screen may be out of date (someone else acted, or an answer was lost), so reload it. */
  refresh: boolean;
  /** The server's request id, shown small so support can find the log line. */
  ref: string | null;
}

/** Consumers are never told about roles, admins or other people acting on their case. */
export type Audience = 'consumer' | 'staff';
let audience: Audience = 'consumer';

/** The app sets this once it knows who is signed in. Until then the consumer wording is used, as the safer one. */
export function setAudience(next: Audience): void {
  audience = next;
}

type Rule = Omit<Described, 'message' | 'ref'> & { fallback: string; keepServerText: boolean };
const rule = (title: string, severity: Described['severity'], fallback: string, flags: Partial<Rule> = {}): Rule =>
  ({ title, severity, fallback, retry: false, refresh: false, keepServerText: true, ...flags });

const CHECK = 'Something in the form is not accepted. Check it and try again.';
const FORBIDDEN: Record<Audience, string> = {
  consumer: 'This is not open to your account.',
  staff: 'Your role cannot do this. Ask an admin if you need it.',
};
const CONFLICT: Record<Audience, string> = {
  consumer: 'This changed since you opened it. Check the latest before you try again.',
  staff: 'Someone else acted on this first. Check the latest before you try again.',
};

// What each answer means for the person. keepServerText says whether an old style (string) detail is worth showing;
// an envelope message is written to be shown, so it is always kept.
const byStatus = (who: Audience): Record<number, Rule> => ({
  400: rule('Check the details', 'error', CHECK),
  401: rule('Signed out', 'warning', 'Your session ended. Sign in again to carry on.', { keepServerText: false }),
  // Staff 403s say what is out of scope; a consumer gets plain words that never mention roles.
  403: rule('Not allowed', 'error', FORBIDDEN[who], { keepServerText: who === 'staff' }),
  404: rule('No longer here', 'warning', 'It may have been moved, closed or removed.', { refresh: true }),
  409: rule('Already changed', 'warning', CONFLICT[who], { refresh: true }),
  413: rule('File too large', 'error', 'Choose a smaller file and try again.'),
  // The old upload check names voice notes even where only photos go, so its sentence is not shown.
  415: rule('File type not accepted', 'error', 'This type of file cannot be sent here. Choose a different file.', { keepServerText: false }),
  422: rule('Check the details', 'error', CHECK),
  429: rule('Too many attempts', 'warning', 'Wait a minute, then try again.'),
});

const LOST: Described = { title: 'No answer from the server', severity: 'warning', retry: false, refresh: true, ref: null,
  message: 'The connection dropped before we heard back, so it may have gone through. Check before you try again.' };
const OFFLINE: Described = { title: 'You are offline', severity: 'warning', retry: true, refresh: false, ref: null,
  message: 'Nothing was sent. Check your connection and try again.' };
const OUR_SIDE = 'Something went wrong on our side. Nothing was changed. Try again in a moment.';
// Old style 502 and 503 details are hand written ("The code could not be sent"); a 500 string may be anything.
const WORDED_5XX = new Set([502, 503]);

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** The envelope's message may end with "Reference ABC123"; the reference is shown on its own line instead. */
function withoutRef(message: string, ref: string | null): string {
  if (!ref || !message.includes(ref)) return message;
  return message.replace(new RegExp(`[^.!?।۔]*${escapeRe(ref)}[^.!?।۔]*[.!?।۔]?\\s*$`), '').trim();
}

function serverSentence(error: ApiError): { text: string; envelope: boolean } {
  return { text: error.serverText ? withoutRef(error.message, error.ref) : '', envelope: error.code !== null };
}

function forServerFault(error: ApiError, action: string): Described {
  const { text, envelope } = serverSentence(error);
  const worded = text && (envelope || WORDED_5XX.has(error.status));
  return { title: `${action} did not go through`, severity: 'error', retry: true, refresh: false, ref: error.ref,
    message: worded ? text : OUR_SIDE };
}

/** What went wrong and what to do now, in plain words, for any failed request. The server's own sentence is kept
 * where it says something specific, and replaced where it would only confuse. A raw JavaScript error is never shown.
 * trustServer keeps an old style detail on any 4xx, for routes whose every refusal is written for the person (sign in
 * codes). */
export function describeError(error: unknown, action = 'That', trustServer = false): Described {
  if (error instanceof NetworkError) return error.sent ? LOST : OFFLINE;
  if (!(error instanceof ApiError)) {
    return { title: `${action} did not go through`, severity: 'error', retry: false, refresh: false, ref: null,
      message: 'Something went wrong. Please try again.' };
  }
  return error.status >= 500 ? forServerFault(error, action) : forRefusal(error, action, trustServer);
}

function forRefusal(error: ApiError, action: string, trustServer: boolean): Described {
  const { text, envelope } = serverSentence(error);
  const found = byStatus(audience)[error.status];
  if (!found) {
    return { title: `${action} did not go through`, severity: 'error', retry: false, refresh: false, ref: error.ref,
      message: text || 'Please try again.' };
  }
  const { fallback, keepServerText, ...said } = found;
  const show = text && (envelope || keepServerText || trustServer);
  return { ...said, ref: error.ref, message: show ? text : fallback };
}
