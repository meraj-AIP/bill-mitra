import PhotoCameraOutlinedIcon from '@mui/icons-material/PhotoCameraOutlined';
import UploadFileOutlinedIcon from '@mui/icons-material/UploadFileOutlined';
import { Box, Button, Stack, Typography } from '@mui/material';
import { useRef, useState, type DragEvent } from 'react';

import { ACCEPTED_TYPES, MAX_MB } from '../api/billsApi';

interface UploadZoneProps {
  onFile: (file: File) => void;
}

/** Drop, browse or (on a phone) open the camera. All three hand one file to onFile. */
export function UploadZone({ onFile }: UploadZoneProps) {
  const browse = useRef<HTMLInputElement | null>(null);
  const camera = useRef<HTMLInputElement | null>(null);
  const [over, setOver] = useState(false);

  const take = (files: FileList | null | undefined) => {
    const file = files?.[0];
    if (file) onFile(file);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    take(e.dataTransfer.files);
  };

  return (
    <Box
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      sx={{
        border: 1.5,
        borderStyle: 'dashed',
        borderColor: over ? 'primary.main' : 'grey.300',
        bgcolor: over ? 'info.light' : 'grey.50',
        borderRadius: 2.5,
        px: { xs: 2, sm: 4 },
        py: { xs: 4, sm: 5 },
        textAlign: 'center',
        transition: 'background-color 200ms, border-color 200ms',
      }}
    >
      <Box sx={{ display: 'inline-grid', placeItems: 'center', width: 52, height: 52, borderRadius: 2, bgcolor: 'background.paper',
        border: 1, borderColor: 'divider', color: 'primary.main', mb: 1.5 }}>
        <UploadFileOutlinedIcon />
      </Box>
      <Typography variant="h3" component="p">
        Drop your bill here
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
        JPG, PNG, WEBP, HEIC or PDF, up to {MAX_MB} MB
      </Typography>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1, justifyContent: 'center', mt: 2.5 }}>
        <Button variant="contained" size="large" onClick={() => browse.current?.click()} startIcon={<UploadFileOutlinedIcon />}>
          Choose a file
        </Button>
        <Button variant="outlined" size="large" onClick={() => camera.current?.click()} startIcon={<PhotoCameraOutlinedIcon />}
          sx={{ display: { md: 'none' } }}>
          Take a photo
        </Button>
      </Stack>
      <Box component="input" type="file" ref={browse} accept={`${ACCEPTED_TYPES.join(',')},.heic,.heif`} sx={{ display: 'none' }}
        onChange={(e) => {
          take(e.currentTarget.files);
          e.currentTarget.value = '';
        }} />
      <Box component="input" type="file" ref={camera} accept="image/jpeg,image/png,image/webp,image/heic,image/heif" capture="environment" sx={{ display: 'none' }}
        onChange={(e) => {
          take(e.currentTarget.files);
          e.currentTarget.value = '';
        }} />
    </Box>
  );
}
