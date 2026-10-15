import { getJson, postForm, postJson, readNdjson } from '@/shared/api/http';
import { shrinkImage } from '@/shared/lib/image';
import type { Language } from '@/shared/lib/languages';

import type { HistoryPage, OutgoingMessage, StreamEvent, Uploaded } from './types';

const PAGE_SIZE = 40;

export async function upload(file: Blob, name: string): Promise<Uploaded> {
  const body = file instanceof File ? await shrinkImage(file) : file;
  const form = new FormData();
  form.append('file', body, name);
  return postForm<Uploaded>('/api/web/upload', form);
}

export async function sendMessage(
  language: Language,
  message: OutgoingMessage,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await postJson('/api/web/messages', { language, ...message });
  await readNdjson(response, (value) => onEvent(value as StreamEvent));
}

export function fetchHistory(before: number | undefined, signal: AbortSignal): Promise<HistoryPage> {
  const query = new URLSearchParams({ limit: String(PAGE_SIZE) });
  if (before !== undefined) query.set('before', String(before));
  return getJson<HistoryPage>(`/api/web/history?${query.toString()}`, signal);
}

/** Starts a new chat and deletes the saved one on the server. */
export async function resetConversation(): Promise<void> {
  await postJson('/api/web/reset');
}

export function mediaUrl(mediaId: string): string {
  return `/api/media/${encodeURIComponent(mediaId)}`;
}
