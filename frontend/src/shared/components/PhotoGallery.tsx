import BrokenImageOutlinedIcon from '@mui/icons-material/BrokenImageOutlined';
import { Box, ButtonBase, Typography } from '@mui/material';
import { useMemo, useState, type ReactNode } from 'react';

import { GalleryContext, usePhotoGallery, type Gallery, type GalleryPhoto } from '@/shared/hooks/usePhotoGallery';

import { Lightbox } from './Lightbox';

interface Shown { list: GalleryPhoto[]; index: number }

/**
 * Every photo on a page in one lightbox, so next and previous walk the conversation, the requests and attached bills
 * together. The list is copied when the lightbox opens, so a background refetch never moves the photo on show.
 */
export function PhotoGallery({ photos, children }: { photos: GalleryPhoto[]; children: ReactNode }) {
  const [shown, setShown] = useState<Shown | null>(null);
  const gallery = useMemo<Gallery>(() => ({
    open: (photo) => {
      const index = photos.findIndex((p) => p.src === photo.src);
      setShown(index >= 0 ? { list: photos, index } : { list: [photo], index: 0 });
    },
  }), [photos]);
  return (
    <GalleryContext value={gallery}>
      {children}
      <Lightbox photos={shown?.list ?? []} index={shown?.index ?? null} onClose={() => setShown(null)}
        onIndex={(index) => setShown((s) => (s ? { ...s, index } : s))} />
    </GalleryContext>
  );
}

/** Drops repeats, so a photo that shows in the thread and in a request counts once. */
export function uniquePhotos(photos: GalleryPhoto[]): GalleryPhoto[] {
  const seen = new Set<string>();
  return photos.filter((p) => (seen.has(p.src) ? false : (seen.add(p.src), true)));
}

const SIZE = { small: { width: 64, height: 64 }, medium: { width: { xs: 160, sm: 200 }, height: { xs: 120, sm: 150 } } };

interface ThumbProps extends GalleryPhoto { size?: keyof typeof SIZE }

/** A photo preview that opens the page's lightbox. Outside a gallery it opens the photo in a new tab. */
export function PhotoThumb({ size = 'medium', ...photo }: ThumbProps) {
  const gallery = usePhotoGallery();
  const [broken, setBroken] = useState(false);
  const open = () => (gallery ? gallery.open(photo) : window.open(photo.src, '_blank', 'noopener'));
  return (
    <ButtonBase onClick={open} aria-label={`Open photo: ${photo.alt}`}
      sx={{ ...SIZE[size], flexShrink: 0, display: 'block', overflow: 'hidden', borderRadius: size === 'small' ? 1 : 1.5,
        border: 1, borderColor: 'divider', bgcolor: 'grey.100', cursor: 'zoom-in', transition: 'border-color 200ms, transform 120ms',
        '&:hover': { borderColor: 'primary.main' }, '&:active': { transform: 'scale(0.98)' },
        '&.Mui-focusVisible': { outline: 2, outlineColor: 'primary.main', outlineOffset: 2 } }}>
      {broken ? (
        <Box sx={{ height: '100%', display: 'grid', placeItems: 'center', alignContent: 'center', gap: 0.5, color: 'text.secondary', p: 1 }}>
          <BrokenImageOutlinedIcon fontSize="small" />
          {size === 'medium' && <Typography variant="caption">Photo did not load</Typography>}
        </Box>
      ) : (
        <Box component="img" src={photo.src} alt={photo.alt} loading="lazy" onError={() => setBroken(true)}
          sx={{ display: 'block', width: '100%', height: '100%', objectFit: 'cover' }} />
      )}
    </ButtonBase>
  );
}
