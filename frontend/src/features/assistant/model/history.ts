import { mediaUrl } from '../api/assistantApi';
import type { HistoryItem, Outbound, ReplyButton, UserBody } from '../api/types';
import type { ThreadItem, UserContent } from './conversation';

/** The server stores "YYYY-MM-DD HH:MM:SS" in UTC with no zone suffix. */
const parseAt = (at: string) => new Date(`${at.replace(' ', 'T')}Z`);

function optionsOf(message: Outbound): ReplyButton[] | null {
  if (message.type === 'buttons') return message.buttons;
  if (message.type === 'list') return message.rows;
  return null;
}

// Only the id is stored; the title lives on the buttons or list the consumer tapped.
function replyTitle(id: string, options: ReplyButton[]): string {
  return options.find((o) => o.id === id)?.title ?? id;
}

function userContent(body: UserBody, options: ReplyButton[]): UserContent {
  const src = body.media_id ? mediaUrl(body.media_id) : '';
  const text = body.text ?? undefined;
  switch (body.kind) {
    case 'image':
      return { kind: 'image', src, caption: text };
    case 'document':
      return { kind: 'document', name: 'PDF document', href: src || undefined };
    case 'audio':
      return { kind: 'audio', src, transcript: body.transcript ?? undefined };
    case 'button_reply':
      return { kind: 'reply', title: replyTitle(body.reply_id ?? '', options) };
    default:
      return { kind: 'text', text: text ?? '' };
  }
}

/** Saved messages (oldest first) as thread items, with tapped button ids turned back into titles. */
export function fromHistory(items: HistoryItem[]): ThreadItem[] {
  let options: ReplyButton[] = [];
  return items.map((item): ThreadItem => {
    const base = { key: `h${item.id}`, at: parseAt(item.at), live: false, serverId: item.id };
    if (item.sender === 'bot') {
      options = optionsOf(item.body) ?? options;
      return { ...base, from: 'bot', message: item.body };
    }
    return { ...base, from: 'user', content: userContent(item.body, options) };
  });
}
