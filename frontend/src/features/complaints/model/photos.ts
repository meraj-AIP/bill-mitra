import type { GalleryPhoto } from '@/shared/hooks/usePhotoGallery';
import { dateTime, shortDate } from '@/shared/lib/format';

import type { ComplaintMessage, ComplaintRequest } from '../api/types';
import { requestLabel } from './labels';

/** A message file the browser can show as a picture. PDFs and other files stay as links. */
export function isPhoto(m: Pick<ComplaintMessage, 'media_url' | 'media_type'>): boolean {
  return Boolean(m.media_url) && (!m.media_type || m.media_type.startsWith('image/'));
}

function who(m: ComplaintMessage): string {
  if (m.author_kind === 'consumer') return 'the consumer';
  return m.author_name ?? 'staff';
}

export function messagePhoto(m: ComplaintMessage): GalleryPhoto | null {
  if (!m.media_url || !isPhoto(m)) return null;
  const when = dateTime(m.created_at);
  return { src: m.media_url, alt: `Photo sent by ${who(m)}, ${when}`, caption: `Sent by ${who(m)}, ${when}` };
}

/** Every photo on a complaint page in reading order: the thread first, then answers to requests. */
export function pagePhotos(messages: ComplaintMessage[], requests: ComplaintRequest[] = []): GalleryPhoto[] {
  const fromThread = messages.map(messagePhoto).filter((p): p is GalleryPhoto => p !== null);
  const fromAnswers = requests.flatMap((r) => (r.answer?.media_url
    ? [{ src: r.answer.media_url, alt: `Photo sent for ${requestLabel(r.kind)}, ${shortDate(r.answer.at)}`,
      caption: `Sent by the consumer for ${requestLabel(r.kind)}, ${shortDate(r.answer.at)}` }]
    : []));
  // A photo that answered a request also sits in the thread; it counts once in the viewer.
  const seen = new Set<string>();
  return [...fromThread, ...fromAnswers].filter((p) => (seen.has(p.src) ? false : (seen.add(p.src), true)));
}
