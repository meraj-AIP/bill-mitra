import type { ComplaintDetail, Person, TimelineEntry } from '../api/types';

/** The person holding the complaint: the hand-off contract's `with`, sent as `assignee`. */
export function holderOf(c: ComplaintDetail): Person | null {
  return c.assignee ?? null;
}

// The server writes hand-offs as "Handed to <name>: <note>". A server that sends the note on its own wins.
const HANDOFF_LINE = /^((?:Handed to|Sent back to|Routed to) [^:]{1,80}):\s+([\s\S]+)$/;

/** The headline and the note of a timeline entry, so the note can be shown as the person wrote it. */
export function splitNote(e: TimelineEntry): { text: string; note: string | null } {
  if (e.note) return { text: e.text, note: e.note };
  const match = HANDOFF_LINE.exec(e.text);
  return match?.[1] && match[2] ? { text: match[1], note: match[2] } : { text: e.text, note: null };
}
