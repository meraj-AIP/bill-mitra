import AutorenewIcon from '@mui/icons-material/Autorenew';
import ContentCopyOutlinedIcon from '@mui/icons-material/ContentCopyOutlined';
import { Button, Stack, TextField } from '@mui/material';
import { useState } from 'react';

import { MIN_PASSWORD } from '@/features/auth';

import { generatePassword } from '../model/labels';

interface InitialPasswordFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error: string | null;
}

/** Shown in clear text on purpose: the admin has to pass it on to the person. */
export function InitialPasswordField({ label, value, onChange, error }: InitialPasswordFieldProps) {
  const [copied, setCopied] = useState<'yes' | 'failed' | null>(null);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied('yes');
    } catch {
      setCopied('failed');
    }
  };

  const helper = error ?? (copied === 'yes' ? 'Copied. Share it with the person directly, not in a group chat.'
    : copied === 'failed' ? 'Could not copy. Select the text and copy it by hand.'
      : `At least ${MIN_PASSWORD} characters. They should change it after signing in.`);

  return (
    <Stack sx={{ gap: 1 }}>
      <TextField label={label} value={value} fullWidth autoComplete="new-password" error={Boolean(error)} helperText={helper}
        onChange={(e) => { setCopied(null); onChange(e.target.value); }}
        slotProps={{ htmlInput: { spellCheck: false, autoCapitalize: 'none', sx: { fontFamily: 'monospace' } } }} />
      <Stack direction="row" sx={{ gap: 1 }}>
        <Button size="small" variant="outlined" startIcon={<AutorenewIcon />} onClick={() => { setCopied(null); onChange(generatePassword()); }}>
          Generate
        </Button>
        <Button size="small" variant="outlined" startIcon={<ContentCopyOutlinedIcon />} disabled={!value} onClick={() => void copy()}>
          Copy
        </Button>
      </Stack>
    </Stack>
  );
}
