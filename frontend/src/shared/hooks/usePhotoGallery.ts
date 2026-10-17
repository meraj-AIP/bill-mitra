import { createContext, useContext } from 'react';

export interface GalleryPhoto {
  src: string;
  /** Says what the photo shows, for screen readers and as the lightbox caption. */
  alt: string;
  /** A short line under the photo, such as who sent it and when. */
  caption?: string;
}

export interface Gallery {
  /** Opens the lightbox at this photo. A photo the page did not list opens on its own. */
  open: (photo: GalleryPhoto) => void;
}

export const GalleryContext = createContext<Gallery | null>(null);

/** Null outside a PhotoGallery; thumbnails then open the photo in a new tab. */
export function usePhotoGallery(): Gallery | null {
  return useContext(GalleryContext);
}
