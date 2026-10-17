import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import UploadFileOutlinedIcon from '@mui/icons-material/UploadFileOutlined';
import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from '@mui/material';
import { useId, useState } from 'react';

import { formatCount } from '@/shared/lib/format';

import { useImportAccounts, type AccountImportResult } from '../api/adminApi';
import { ACCOUNT_CSV_COLUMNS, ACCOUNT_TEMPLATE_HREF } from '../model/csv';
import { ImportedAccounts } from './ImportedAccounts';
import { ImportErrors } from './ImportErrors';

function Summary({ result }: { result: AccountImportResult }) {
  const created = result.created.length;
  const skipped = result.errors.length;
  return (
    <Alert severity={skipped === 0 ? 'success' : created === 0 ? 'error' : 'warning'} role="status">
      {formatCount(created)} {created === 1 ? 'account' : 'accounts'} created.
      {skipped > 0 && ` ${formatCount(skipped)} ${skipped === 1 ? 'line was' : 'lines were'} skipped. Fix them and import only those lines again.`}
    </Alert>
  );
}

function Results({ result }: { result: AccountImportResult }) {
  return (
    <>
      <Summary result={result} />
      {result.created.length > 0 && <ImportedAccounts rows={result.created} />}
      {result.errors.length > 0 && <ImportErrors errors={result.errors} />}
    </>
  );
}

const closeLabel = (holdsPasswords: boolean, done: boolean) => (holdsPasswords ? 'I have saved them, close' : done ? 'Done' : 'Cancel');

function ChooseFile({ file, onFile }: { file: File | null; onFile: (file: File | null) => void }) {
  const inputId = useId();
  return (
    <>
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
        One staff member per line. The role is a role slug from the Roles page and the unit is the unit code. Each person gets a
        random password, shown once after the import. Up to 500 lines and 1 MB.
      </Typography>
      <Box component="code" sx={{ display: 'block', p: 1.5, borderRadius: 1, bgcolor: 'grey.100', fontSize: '0.8125rem', overflowX: 'auto' }}>
        {ACCOUNT_CSV_COLUMNS}
      </Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1 }}>
        <Button variant="outlined" startIcon={<FileDownloadOutlinedIcon />} href={ACCOUNT_TEMPLATE_HREF} download="bill-mitra-staff-template.csv">
          Download template
        </Button>
        <Button variant="outlined" component="label" htmlFor={inputId} startIcon={<UploadFileOutlinedIcon />}>
          {file ? 'Choose another file' : 'Choose CSV file'}
          <Box component="input" id={inputId} type="file" accept=".csv,text/csv" hidden onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
        </Button>
      </Stack>
      {file && <Typography variant="body2">Selected: <b>{file.name}</b></Typography>}
    </>
  );
}

/**
 * Creates many staff accounts from one CSV. The result, passwords included, lives only in the mutation while this
 * dialog is open; closing it unmounts the dialog and the cache entry goes with it.
 */
export function ImportAccountsDialog({ onClose }: { onClose: () => void }) {
  const upload = useImportAccounts();
  const [file, setFile] = useState<File | null>(null);
  const result = upload.data;
  const holdsPasswords = (result?.created.length ?? 0) > 0;
  // While importing, or once passwords are on screen, only the button closes, so a stray click cannot lose them.
  const locked = holdsPasswords || upload.isPending;
  const close = (_e?: unknown, reason?: string) => {
    if (locked && reason) return;
    upload.reset();
    onClose();
  };

  return (
    <Dialog open onClose={close} fullWidth maxWidth="md">
      <DialogTitle>Import staff accounts from a CSV file</DialogTitle>
      <DialogContent>
        <Stack sx={{ gap: 2 }}>
          {!holdsPasswords && <ChooseFile file={file} onFile={(f) => { setFile(f); upload.reset(); }} />}
          {upload.error && <Alert severity="error">{upload.error.message}</Alert>}
          {result && <Results result={result} />}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={() => close()} disabled={upload.isPending}>{closeLabel(holdsPasswords, Boolean(result))}</Button>
        {!holdsPasswords && (
          <Button variant="contained" disabled={!file || upload.isPending} onClick={() => file && upload.mutate(file)}
            startIcon={upload.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
            {upload.isPending ? 'Importing' : 'Import'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
