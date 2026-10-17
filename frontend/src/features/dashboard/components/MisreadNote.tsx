import ManageSearchOutlinedIcon from '@mui/icons-material/ManageSearchOutlined';
import { Alert, AlertTitle, Box, Button } from '@mui/material';
import { Link } from 'react-router-dom';

import { monthLabel } from '@/shared/lib/format';
import type { Language } from '@/shared/lib/languages';

import type { Misread } from '../api/types';

/** Calm on purpose: it states what the two bills print and offers the earlier bill, where the report is made. */
export function MisreadNote({ misread, language }: { misread: Misread; language: Language }) {
  const month = monthLabel(misread.earlier_month);
  const to = `/bills/${encodeURIComponent(misread.earlier_bill_id)}${language === 'te' ? '' : `?lang=${language}`}`;
  return (
    <Alert severity="info" variant="outlined" icon={<ManageSearchOutlinedIcon />}>
      <AlertTitle sx={{ fontWeight: 600 }}>Your {month} bill may have been read too high</AlertTitle>
      <Box component="span">
        This bill starts from a meter reading of {misread.next_previous}. Your {month} bill printed {misread.printed_present} as
        its present reading. A meter cannot run backwards, so the {month} bill was likely read higher than the meter showed.
        You can report it from that bill and we will check it.
      </Box>
      <Box sx={{ mt: 1.5 }}>
        <Button component={Link} to={to} color="inherit" size="small" variant="outlined">Open the {month} bill</Button>
      </Box>
    </Alert>
  );
}
