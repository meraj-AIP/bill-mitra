import { ApiError } from '@/shared/api/http';
import { describeError } from '@/shared/feedback';

/** The server's own sentence for a refused code is the useful one ("not registered with TGSPDCL", "wait 30
 * minutes"), so it is shown as is. Anything else gets the usual plain wording. */
export function codeProblem(error: Error | null): string | null {
  if (!error) return null;
  if (error instanceof ApiError && [400, 403, 404, 429, 502, 503].includes(error.status)) return error.message;
  return describeError(error, 'Signing in').message;
}

export const CHANNEL_LABEL = { sms: 'Text message (SMS)', whatsapp: 'WhatsApp' } as const;

export const PHONE_AGENT = /Android|iPhone|iPad|iPod|Mobile/i;
