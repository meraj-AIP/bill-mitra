import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import AddCommentOutlinedIcon from '@mui/icons-material/AddCommentOutlined';
import TranslateIcon from '@mui/icons-material/Translate';
import { Button, InputAdornment, MenuItem, Stack, TextField } from '@mui/material';

import { PageHeader } from '@/shared/components/PageHeader';

import type { Language } from '../api/types';
import { LANGUAGES } from '../model/strings';

interface AssistantHeaderProps {
  staff: boolean;
  language: Language;
  onLanguage: (language: Language) => void;
  onNewChat: () => void;
  /** Phones and tablets open the trace in a drawer; wide screens show it beside the chat. */
  onTrace?: (() => void) | undefined;
}

export function AssistantHeader({ staff, language, onLanguage, onNewChat, onTrace }: AssistantHeaderProps) {
  const lead = staff
    ? 'The same chat a consumer gets on WhatsApp. Every reply here is a message WhatsApp can deliver.'
    : 'Send your bill and ask anything about it in Telugu, English, Hindi or Urdu.';
  return (
    <PageHeader
      eyebrow={staff ? 'Consumer preview' : 'Bill Mitra'}
      title="Assistant"
      lead={lead}
      actions={
        <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField select size="small" value={language} onChange={(e) => onLanguage(e.target.value as Language)}
            label="Reply language" sx={{ minWidth: 168, '& .MuiInputBase-root': { bgcolor: 'background.paper' } }}
            slotProps={{ input: { startAdornment: <InputAdornment position="start"><TranslateIcon fontSize="small" /></InputAdornment> } }}>
            {LANGUAGES.map((l) => <MenuItem key={l.code} value={l.code} lang={l.code}>{l.label}</MenuItem>)}
          </TextField>
          <Button variant="outlined" startIcon={<AddCommentOutlinedIcon />} onClick={onNewChat} sx={{ bgcolor: 'background.paper', height: 40 }}>
            New chat
          </Button>
          {onTrace && (
            <Button variant="outlined" startIcon={<AccountTreeOutlinedIcon />} onClick={onTrace} sx={{ bgcolor: 'background.paper', height: 40 }}>
              Behind the reply
            </Button>
          )}
        </Stack>
      }
    />
  );
}
