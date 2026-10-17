import type { GalleryPhoto } from '@/shared/hooks/usePhotoGallery';
import { dateTime } from '@/shared/lib/format';

import type { MyMessage } from '../api/types';

/** Staff never appear by name here: every reply reads as Bill Mitra. */
export function myPhoto(m: MyMessage): GalleryPhoto | null {
  if (!m.media_url || (m.media_type && !m.media_type.startsWith('image/'))) return null;
  const who = m.from === 'you' ? 'You sent this photo' : 'Photo from Bill Mitra';
  return { src: m.media_url, alt: `${who}, ${dateTime(m.at)}`, caption: `${who}, ${dateTime(m.at)}` };
}

export function myPhotos(messages: MyMessage[]): GalleryPhoto[] {
  return messages.map(myPhoto).filter((p): p is GalleryPhoto => p !== null);
}
