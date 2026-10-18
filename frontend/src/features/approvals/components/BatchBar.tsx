import DoneAllRoundedIcon from '@mui/icons-material/DoneAllRounded';
import { Button, Checkbox, CircularProgress, FormControlLabel, Paper, Stack } from '@mui/material';

interface Props {
  onPage: number;
  chosen: number;
  busy: boolean;
  onAll: (on: boolean) => void;
  onApprove: () => void;
}

/** Select what is on this page and approve it in one go. Each one is still checked and carried out on its own. */
export function BatchBar({ onPage, chosen, busy, onAll, onApprove }: Props) {
  if (onPage === 0) return null;
  return (
    <Paper variant="outlined" sx={{ px: 2, py: 1, position: 'sticky', top: { xs: 104, md: 112 }, zIndex: 1, bgcolor: 'background.paper' }}>
      <Stack direction="row" sx={{ gap: 2, alignItems: 'center', justifyContent: 'space-between' }}>
        <FormControlLabel label={chosen ? `${chosen} selected` : 'Select all on this page'}
          control={<Checkbox checked={chosen === onPage} indeterminate={chosen > 0 && chosen < onPage} onChange={(e) => onAll(e.target.checked)} />} />
        <Button variant="contained" disabled={!chosen || busy} onClick={onApprove}
          startIcon={busy ? <CircularProgress size={16} color="inherit" aria-hidden /> : <DoneAllRoundedIcon />}>
          {chosen ? `Approve ${chosen}` : 'Approve selected'}
        </Button>
      </Stack>
    </Paper>
  );
}
