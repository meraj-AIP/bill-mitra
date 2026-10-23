import { describeError } from '@/shared/feedback';

/** Every refusal on the sign in code routes is written for the person ("not registered with TGSPDCL", "wait 30
 * minutes"), so the server's own sentence is kept. Anything else gets the usual plain wording. */
export function codeProblem(error: Error | null): string | null {
  return error ? describeError(error, 'Signing in', true).message : null;
}

export const CHANNEL_LABEL = { sms: 'Text message (SMS)', whatsapp: 'WhatsApp' } as const;

export const PHONE_AGENT = /Android|iPhone|iPad|iPod|Mobile/i;
