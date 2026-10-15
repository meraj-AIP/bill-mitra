import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material';
import { useState } from 'react';

import type { Language } from '@/shared/lib/languages';
import { checkPhoto, type PhotoIssue } from '@/shared/lib/photoCheck';

import { LanguageSelect } from './LanguageSelect';
import { UploadZone } from './UploadZone';

interface UploadCardProps {
  language: Language;
  onLanguage: (language: Language) => void;
  error: string | null;
  onDismiss: () => void;
  onFile: (file: File) => void;
}

const ISSUE: Record<PhotoIssue, string> = {
  small: 'This photo is quite small, so the numbers may be hard to read.',
  dark: 'This photo looks dark, so the numbers may be hard to read.',
  blurry: 'This photo looks blurred, so the numbers may be hard to read.',
};

export function UploadCard({ language, onLanguage, error, onDismiss, onFile }: UploadCardProps) {
  const [doubt, setDoubt] = useState<{ file: File; issue: PhotoIssue } | null>(null);
  const take = async (file: File) => {
    const issue = await checkPhoto(file);
    if (issue) setDoubt({ file, issue });
    else onFile(file);
  };
  return (
    <Paper variant="outlined" component="section" aria-labelledby="upload-title" sx={{ p: { xs: 2, sm: 3 } }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2, mb: 2.5, alignItems: { sm: 'center' } }}>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h2" id="upload-title">Upload a bill</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>Pick the language for the explanation.</Typography>
        </Box>
        <LanguageSelect value={language} onChange={onLanguage} />
      </Stack>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={onDismiss}>
          {error}
        </Alert>
      )}
      {doubt && (
        <Alert severity="warning" sx={{ mb: 2 }}
          action={
            <Stack direction="row" sx={{ gap: 1 }}>
              <Button color="inherit" size="small" onClick={() => setDoubt(null)}>Choose another</Button>
              <Button color="inherit" size="small" onClick={() => { onFile(doubt.file); setDoubt(null); }}>Use it anyway</Button>
            </Stack>
          }>
          {ISSUE[doubt.issue]} Hold the phone steady over the whole bill, in good light.
        </Alert>
      )}
      <UploadZone onFile={(file) => void take(file)} />
    </Paper>
  );
}
