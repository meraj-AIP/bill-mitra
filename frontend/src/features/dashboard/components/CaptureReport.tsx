import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlineOutlined';
import HelpOutlineIcon from '@mui/icons-material/HelpOutlineOutlined';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutlineOutlined';
import { Box, Chip, LinearProgress, Stack, Typography } from '@mui/material';

import type { Capture } from '../api/types';
import { captureValue } from '../model/captureValue';
import { ReportSection } from './ReportSection';

const FIELD_ICON = {
  captured: <CheckCircleOutlineIcon sx={{ fontSize: 18, color: 'success.main' }} />,
  missing: <RemoveCircleOutlineIcon sx={{ fontSize: 18, color: 'text.disabled' }} />,
  unreadable: <HelpOutlineIcon sx={{ fontSize: 18, color: 'warning.main' }} />,
};

const CHECK_CHIP = {
  pass: { label: 'Pass', color: 'success' },
  fail: { label: 'Fail', color: 'error' },
  skipped: { label: 'Skipped', color: 'default' },
} as const;

function FieldRow({ field }: { field: Capture['fields'][number] }) {
  const value = field.status === 'captured' ? (field.value === null ? 'Read' : captureValue(field.key, field.value)) : field.status === 'missing' ? 'Not on the bill' : 'Could not read';
  return (
    <Stack component="li" direction="row" sx={{ gap: 1, py: 0.75, alignItems: 'flex-start', borderBottom: 1, borderColor: 'divider' }}>
      <Box sx={{ pt: 0.125, display: 'flex' }} aria-label={field.status}>{FIELD_ICON[field.status]}</Box>
      <Typography variant="body2" sx={{ flex: 1, color: 'text.secondary' }}>{field.label}</Typography>
      <Typography variant="body2" sx={{ fontWeight: field.status === 'captured' ? 600 : 400, textAlign: 'right',
        color: field.status === 'captured' ? 'text.primary' : 'text.secondary', fontVariantNumeric: 'tabular-nums', overflowWrap: 'anywhere' }}>
        {value}
      </Typography>
    </Stack>
  );
}

/** Answers "did we read everything": every expected field and every cross-check on the numbers. */
export function CaptureReport({ capture, confidence }: { capture: Capture; confidence: number | null }) {
  const ratio = capture.expected ? (capture.captured / capture.expected) * 100 : 0;
  return (
    <ReportSection
      title={`Captured ${capture.captured} of ${capture.expected} fields`}
      caption={confidence === null ? undefined : `Reader confidence ${Math.round(confidence * 100)}%`}
    >
      <LinearProgress variant="determinate" value={ratio} aria-label="Fields captured" sx={{ height: 6, mb: 1.5 }} />
      <Box component="ul" sx={{ m: 0, p: 0, listStyle: 'none', columnGap: 4, columns: { xs: 1, sm: 2 }, '& li': { breakInside: 'avoid' } }}>
        {capture.fields.map((f) => <FieldRow key={f.key} field={f} />)}
      </Box>
      {capture.checks.length > 0 && (
        <>
          <Typography variant="subtitle1" component="h3" sx={{ mt: 2.5, mb: 0.5 }}>Consistency checks</Typography>
          <Stack component="ul" sx={{ m: 0, p: 0, listStyle: 'none' }}>
            {capture.checks.map((c) => (
              <Stack component="li" key={c.key} direction="row" sx={{ gap: 1.5, py: 1, borderBottom: 1, borderColor: 'divider', alignItems: 'flex-start' }}>
                <Chip size="small" variant="outlined" label={CHECK_CHIP[c.status].label} color={CHECK_CHIP[c.status].color} sx={{ minWidth: 64 }} />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{c.label}</Typography>
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>{c.detail}</Typography>
                </Box>
              </Stack>
            ))}
          </Stack>
        </>
      )}
    </ReportSection>
  );
}
