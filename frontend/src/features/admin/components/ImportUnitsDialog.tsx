import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import UploadFileOutlinedIcon from '@mui/icons-material/UploadFileOutlined';
import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from '@mui/material';
import { useId, useState } from 'react';

import { SendStatus } from '@/shared/components/SendStatus';
import { formatCount } from '@/shared/lib/format';

import { CSV_COLUMNS, CSV_TEMPLATE, useImportUnits, type ImportResult } from '../api/unitsApi';
import { ImportErrors } from './ImportErrors';

const TEMPLATE_HREF = `data:text/csv;charset=utf-8,${encodeURIComponent(`${CSV_TEMPLATE}\n`)}`;

function Result({ result }: { result: ImportResult }) {
  const clean = result.errors.length === 0;
  return (
    <Stack sx={{ gap: 1.5 }} role="status">
      <Alert severity={clean ? 'success' : 'warning'}>
        {formatCount(result.created)} added and {formatCount(result.updated)} updated.
        {clean ? ' Every line was read.' : ` ${formatCount(result.errors.length)} lines were skipped; fix them and import the file again.`}
      </Alert>
      {!clean && <ImportErrors errors={result.errors} />}
    </Stack>
  );
}

/** A CSV upload adds or updates many units at once; rows link by code, so parents can come earlier in the same file. */
export function ImportUnitsDialog({ onClose }: { onClose: () => void }) {
  const upload = useImportUnits();
  const [file, setFile] = useState<File | null>(null);
  const inputId = useId();
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Import units from a CSV file</DialogTitle>
      <DialogContent>
        <Stack sx={{ gap: 2 }}>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            One unit per line, with the columns below. Aliases are separated by semicolons. A row whose code already exists updates that unit.
          </Typography>
          <Box component="code" sx={{ display: 'block', p: 1.5, borderRadius: 1, bgcolor: 'grey.100', fontSize: '0.8125rem', overflowX: 'auto' }}>
            {CSV_COLUMNS}
          </Box>
          <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1 }}>
            <Button variant="outlined" startIcon={<FileDownloadOutlinedIcon />} href={TEMPLATE_HREF} download="bill-mitra-units-template.csv">
              Download template
            </Button>
            <Button variant="outlined" component="label" htmlFor={inputId} startIcon={<UploadFileOutlinedIcon />}>
              {file ? 'Choose another file' : 'Choose CSV file'}
              <Box component="input" id={inputId} type="file" accept=".csv,text/csv" hidden
                onChange={(e) => { setFile(e.target.files?.[0] ?? null); upload.reset(); }} />
            </Button>
          </Stack>
          {file && <Typography variant="body2">Selected: <b>{file.name}</b></Typography>}
          <SendStatus state={upload} onTryAgain={file ? () => upload.mutate(file) : undefined} />
          {upload.data && <Result result={upload.data} />}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>{upload.data ? 'Done' : 'Cancel'}</Button>
        <Button variant="contained" disabled={!file || upload.isPending} onClick={() => file && upload.mutate(file)}
          startIcon={upload.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
          {upload.isPending ? 'Importing' : 'Import'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
