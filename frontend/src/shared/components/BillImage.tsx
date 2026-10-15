import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import { Box, Button, ButtonBase, Dialog, IconButton, Paper, Stack, Typography } from '@mui/material';
import { useState } from 'react';

interface BillImageProps {
  src: string;
  isPdf: boolean;
  name?: string;
  /** Staff see someone else's bill, so the heading should not say "your". */
  heading?: string;
  /** Called when the file will not load as an image, for callers that do not know its type. */
  onImageError?: () => void;
}

/** The uploaded bill, next to the report so every figure can be checked against the paper. */
export function BillImage({ src, isPdf, name = 'Uploaded bill', heading, onImageError }: BillImageProps) {
  const [open, setOpen] = useState(false);
  return (
    <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
      <Stack direction="row" sx={{ px: 2, py: 1.25, gap: 1, alignItems: 'center', borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="subtitle2" sx={{ flex: 1 }} noWrap>
          {heading ?? (isPdf ? 'Your bill (PDF)' : 'Your bill photo')}
        </Typography>
        {!isPdf && (
          <Button size="small" startIcon={<ZoomInIcon />} onClick={() => setOpen(true)}>
            Full size
          </Button>
        )}
        <Button size="small" startIcon={<OpenInNewIcon />} href={src} target="_blank" rel="noopener noreferrer">
          Open
        </Button>
      </Stack>
      {isPdf ? (
        <Box component="object" data={src} type="application/pdf" aria-label={name}
          sx={{ display: 'block', width: '100%', height: { xs: 420, md: '70dvh' }, bgcolor: 'grey.100' }}>
          <Typography variant="body2" sx={{ p: 2 }}>
            This browser cannot show the PDF here. Use Open to view it.
          </Typography>
        </Box>
      ) : (
        <ButtonBase onClick={() => setOpen(true)} aria-label="Open the bill photo at full size"
          sx={{ display: 'block', width: '100%', bgcolor: 'grey.100', cursor: 'zoom-in' }}>
          <Box component="img" src={src} alt={name} onError={onImageError}
            sx={{ display: 'block', width: '100%', maxHeight: { xs: 420, md: '70dvh' }, objectFit: 'contain' }} />
        </ButtonBase>
      )}
      <Dialog open={open} onClose={() => setOpen(false)} fullScreen aria-label="Bill photo at full size">
        <Stack direction="row" sx={{ px: 2, py: 1, alignItems: 'center', borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle1" sx={{ flex: 1 }}>{heading ?? 'Your bill photo'}</Typography>
          <IconButton onClick={() => setOpen(false)} aria-label="Close">
            <CloseIcon />
          </IconButton>
        </Stack>
        <Box sx={{ flex: 1, overflow: 'auto', bgcolor: 'grey.900', p: { xs: 1, md: 3 } }}>
          <Box component="img" src={src} alt={name} sx={{ display: 'block', maxWidth: 'none', width: { xs: '160%', md: 'auto' }, mx: 'auto' }} />
        </Box>
      </Dialog>
    </Paper>
  );
}
