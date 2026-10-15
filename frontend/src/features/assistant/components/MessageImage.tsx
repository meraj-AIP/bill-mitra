import CloseIcon from '@mui/icons-material/Close';
import { Box, ButtonBase, Dialog, IconButton } from '@mui/material';
import { useState } from 'react';

interface MessageImageProps {
  src: string;
  alt: string;
  width: number;
}

/** An image in a bubble. Tapping it opens the full size picture, as WhatsApp does. */
export function MessageImage({ src, alt, width }: MessageImageProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <ButtonBase onClick={() => setOpen(true)} aria-label={`${alt}. Open full size`}
        sx={{ display: 'block', borderRadius: '8px', overflow: 'hidden', '&.Mui-focusVisible': { outline: 2, outlineColor: 'primary.main', outlineOffset: 2 } }}>
        <Box component="img" src={src} alt={alt} loading="lazy"
          sx={{ display: 'block', width, maxWidth: '100%', maxHeight: 320, objectFit: 'cover', bgcolor: 'grey.200' }} />
      </ButtonBase>
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="lg" aria-label={alt}
        slotProps={{ paper: { sx: { bgcolor: 'transparent', boxShadow: 'none', m: 2, overflow: 'visible' } } }}>
        <IconButton onClick={() => setOpen(false)} aria-label="Close image"
          sx={{ position: 'absolute', top: -44, right: 0, color: 'common.white' }}>
          <CloseIcon />
        </IconButton>
        <Box component="img" src={src} alt={alt}
          sx={{ display: 'block', maxWidth: '100%', maxHeight: 'calc(100dvh - 120px)', borderRadius: 1.5 }} />
      </Dialog>
    </>
  );
}
