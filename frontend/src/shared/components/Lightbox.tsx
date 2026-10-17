import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import RotateRightIcon from '@mui/icons-material/RotateRight';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import { Box, CircularProgress, Dialog, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';

import { MAX_ZOOM, MIN_ZOOM, useLightboxView, type View } from '@/shared/hooks/useLightboxView';
import type { GalleryPhoto } from '@/shared/hooks/usePhotoGallery';

const ON_DARK = { color: 'common.white', '&.Mui-disabled': { color: 'grey.600' }, '&:hover': { bgcolor: 'grey.800' } };

function Tool({ label, onClick, disabled, children, href }: { label: string; onClick?: () => void; disabled?: boolean; children: ReactNode; href?: string }) {
  return (
    <Tooltip title={label}>
      <span>
        {href ? (
          <IconButton aria-label={label} href={href} target="_blank" rel="noopener noreferrer" sx={ON_DARK}>{children}</IconButton>
        ) : (
          <IconButton aria-label={label} onClick={onClick} disabled={disabled ?? false} sx={ON_DARK}>{children}</IconButton>
        )}
      </span>
    </Tooltip>
  );
}

function Side({ side, onClick }: { side: 'left' | 'right'; onClick: () => void }) {
  return (
    <IconButton aria-label={side === 'left' ? 'Previous photo' : 'Next photo'} onClick={onClick}
      sx={{ ...ON_DARK, position: 'absolute', top: '50%', transform: 'translateY(-50%)', [side]: { xs: 4, sm: 16 }, zIndex: 1,
        bgcolor: 'grey.900', width: 48, height: 48, display: { xs: 'none', sm: 'inline-flex' } }}>
      {side === 'left' ? <ChevronLeftIcon /> : <ChevronRightIcon />}
    </IconButton>
  );
}

type ViewControls = ReturnType<typeof useLightboxView>;

function Picture({ photo, view, dragging }: { photo: GalleryPhoto; view: View; dragging: boolean }) {
  const [status, setStatus] = useState<'loading' | 'ready' | 'failed'>('loading');
  // A quarter turn swaps width and height, so the limits swap too and the photo still fits.
  const quarter = view.rotation % 180 !== 0;
  return (
    <>
      {status === 'loading' && <CircularProgress aria-label="Loading the photo" sx={{ position: 'absolute', color: 'grey.400' }} />}
      {status === 'failed' && (
        <Typography role="alert" variant="body2" sx={{ position: 'absolute', color: 'grey.300', px: 3, textAlign: 'center' }}>
          This photo could not be loaded. Try Open the original, or close and try again.
        </Typography>
      )}
      <Box component="img" src={photo.src} alt={photo.alt} draggable={false}
        onLoad={() => setStatus('ready')} onError={() => setStatus('failed')}
        sx={{ display: status === 'failed' ? 'none' : 'block', objectFit: 'contain', pointerEvents: 'none',
          maxWidth: quarter ? 'calc(100dvh - 140px)' : '100%', maxHeight: quarter ? '100vw' : '100%',
          opacity: status === 'ready' ? 1 : 0,
          transform: `translate(${view.x}px, ${view.y}px) scale(${view.zoom}) rotate(${view.rotation}deg)`,
          transition: dragging ? 'opacity 200ms' : 'transform 180ms ease-out, opacity 200ms' }} />
    </>
  );
}

function cursorFor(zoom: number, dragging: boolean): string {
  if (zoom <= MIN_ZOOM) return 'zoom-in';
  return dragging ? 'grabbing' : 'grab';
}

function Toolbar({ title, titleId, src, view: v, onClose }: { title: string; titleId: string; src: string; view: ViewControls; onClose: () => void }) {
  return (
    <Stack direction="row" sx={{ px: { xs: 1, sm: 2 }, py: 0.75, gap: 0.5, alignItems: 'center', borderBottom: 1, borderColor: 'grey.800' }}>
      <Typography id={titleId} variant="subtitle1" component="h2" noWrap sx={{ flex: 1, minWidth: 0, pl: 1 }}>{title}</Typography>
      <Tool label="Zoom out" onClick={v.zoomOut} disabled={v.view.zoom <= MIN_ZOOM}><ZoomOutIcon /></Tool>
      <Tool label="Zoom in" onClick={v.zoomIn} disabled={v.view.zoom >= MAX_ZOOM}><ZoomInIcon /></Tool>
      <Tool label="Rotate" onClick={v.rotate}><RotateRightIcon /></Tool>
      <Tool label="Open the original" href={src}><OpenInNewIcon /></Tool>
      <Tool label="Close" onClick={onClose}><CloseIcon /></Tool>
    </Stack>
  );
}

function Caption({ id, text }: { id: string; text: string }) {
  return (
    <Box id={id} sx={{ px: 2, py: 1.25, borderTop: 1, borderColor: 'grey.800', textAlign: 'center' }}>
      <Typography variant="body2" sx={{ color: 'grey.200' }}>{text}</Typography>
      <Typography variant="caption" sx={{ color: 'grey.500', display: { xs: 'none', sm: 'block' } }}>
        Arrow keys move between photos. Plus and minus zoom, R rotates, Escape closes.
      </Typography>
      <Typography variant="caption" sx={{ color: 'grey.500', display: { xs: 'block', sm: 'none' } }}>
        Swipe for the next photo. Pinch or double tap to zoom.
      </Typography>
    </Box>
  );
}

interface BodyProps { photos: GalleryPhoto[]; index: number; titleId: string; onIndex: (i: number) => void; onClose: () => void }

/** Keyed by photo, so zoom, rotation and the loading state start fresh on each one. */
function LightboxBody({ photos, index, titleId, onIndex, onClose }: BodyProps) {
  const photo = photos[index];
  const many = photos.length > 1;
  const go = (step: 1 | -1) => { if (many) onIndex((index + step + photos.length) % photos.length); };
  const v = useLightboxView(go);
  const frame = useRef<HTMLDivElement>(null);
  // The dialog focuses its own outer box, above this one, so keys would never reach the handler here.
  useEffect(() => frame.current?.focus(), []);
  if (!photo) return null;

  const keys: Record<string, () => void> = {
    ArrowRight: () => go(1), ArrowLeft: () => go(-1), '+': v.zoomIn, '=': v.zoomIn, '-': v.zoomOut, '0': v.reset, r: v.rotate, R: v.rotate,
  };
  const onKeyDown = (e: KeyboardEvent) => {
    const action = keys[e.key];
    if (!action || e.altKey || e.ctrlKey || e.metaKey) return;
    e.preventDefault();
    action();
  };
  return (
    <Stack ref={frame} tabIndex={-1} onKeyDown={onKeyDown} sx={{ height: '100%', bgcolor: 'grey.900', color: 'common.white', '&:focus': { outline: 'none' } }}>
      <Toolbar title={many ? `Photo ${index + 1} of ${photos.length}` : 'Photo'} titleId={titleId} src={photo.src} view={v} onClose={onClose} />
      <Box {...v.handlers} aria-describedby={`${titleId}-caption`}
        sx={{ position: 'relative', flex: 1, minHeight: 0, overflow: 'hidden', display: 'grid', placeItems: 'center', touchAction: 'none',
          cursor: cursorFor(v.view.zoom, v.dragging), userSelect: 'none' }}>
        {many && <Side side="left" onClick={() => go(-1)} />}
        <Picture photo={photo} view={v.view} dragging={v.dragging} />
        {many && <Side side="right" onClick={() => go(1)} />}
      </Box>
      <Caption id={`${titleId}-caption`} text={photo.caption ?? photo.alt} />
    </Stack>
  );
}

interface LightboxProps {
  photos: GalleryPhoto[];
  /** The photo on show, or null when closed. */
  index: number | null;
  onIndex: (index: number) => void;
  onClose: () => void;
}

/** Full screen viewer. The dialog traps focus and closes on Escape; focus goes back to the thumbnail that opened it. */
export function Lightbox({ photos, index, onIndex, onClose }: LightboxProps) {
  const titleId = useId();
  const open = index !== null && index < photos.length;
  return (
    <Dialog open={open} onClose={onClose} fullScreen aria-labelledby={titleId}
      slotProps={{ paper: { sx: { bgcolor: 'grey.900' } } }}>
      {open && <LightboxBody key={`${index}-${photos[index]?.src ?? ''}`} photos={photos} index={index} titleId={titleId} onIndex={onIndex} onClose={onClose} />}
    </Dialog>
  );
}
