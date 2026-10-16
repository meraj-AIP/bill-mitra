import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import { Button, Popover, Stack, TextField, Typography } from '@mui/material';
import { useId, useState } from 'react';

import { revisionsCsvUrl } from '../api/reviewApi';

/** Every approved revision in scope as CSV, optionally for a date range. The download itself is audited. */
export function ExportRevisions() {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [range, setRange] = useState({ from: '', to: '' });
  const id = useId();
  const backwards = Boolean(range.from && range.to && range.from > range.to);
  return (
    <>
      <Button variant="outlined" startIcon={<FileDownloadOutlinedIcon />} onClick={(e) => setAnchor(e.currentTarget)}
        aria-haspopup="dialog" aria-controls={anchor ? id : undefined}>
        Export revisions
      </Button>
      <Popover id={id} open={Boolean(anchor)} anchorEl={anchor} onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { variant: 'outlined', sx: { p: 2, mt: 0.5, width: 320 } } }}>
        <Typography variant="subtitle2" component="h2">Revisions CSV</Typography>
        <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mb: 2 }}>
          Leave the dates empty for every revision in your units.
        </Typography>
        <Stack direction="row" sx={{ gap: 1 }}>
          <TextField type="date" size="small" label="From" value={range.from} onChange={(e) => setRange((r) => ({ ...r, from: e.target.value }))}
            slotProps={{ inputLabel: { shrink: true } }} />
          <TextField type="date" size="small" label="To" value={range.to} onChange={(e) => setRange((r) => ({ ...r, to: e.target.value }))}
            slotProps={{ inputLabel: { shrink: true } }} error={backwards} />
        </Stack>
        {backwards && <Typography variant="caption" sx={{ color: 'error.main' }}>The end date is before the start date.</Typography>}
        <Button variant="contained" fullWidth sx={{ mt: 2 }} href={revisionsCsvUrl(range)} download disabled={backwards}
          onClick={() => setAnchor(null)}>
          Download CSV
        </Button>
      </Popover>
    </>
  );
}
