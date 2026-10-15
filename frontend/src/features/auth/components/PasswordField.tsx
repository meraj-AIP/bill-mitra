import VisibilityOffOutlinedIcon from '@mui/icons-material/VisibilityOffOutlined';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import { IconButton, InputAdornment, TextField, type TextFieldProps } from '@mui/material';
import { useState } from 'react';

type PasswordFieldProps = Omit<TextFieldProps, 'type' | 'autoComplete'> & {
  autoComplete: 'current-password' | 'new-password';
};

export function PasswordField({ autoComplete, slotProps, ...props }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  return (
    <TextField
      {...props}
      type={visible ? 'text' : 'password'}
      autoComplete={autoComplete}
      slotProps={{
        ...slotProps,
        htmlInput: { spellCheck: false, autoCapitalize: 'none' },
        input: {
          endAdornment: (
            <InputAdornment position="end">
              <IconButton edge="end" onClick={() => setVisible((v) => !v)}
                aria-label={visible ? 'Hide password' : 'Show password'} aria-pressed={visible}>
                {visible ? <VisibilityOffOutlinedIcon fontSize="small" /> : <VisibilityOutlinedIcon fontSize="small" />}
              </IconButton>
            </InputAdornment>
          ),
        },
      }}
    />
  );
}
