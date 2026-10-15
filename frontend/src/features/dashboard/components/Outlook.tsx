import { Alert, Box, Stack, Typography } from '@mui/material';

import { formatCount, monthLabel, rupees } from '@/shared/lib/format';
import { isRtl, type Language } from '@/shared/lib/languages';

import type { Analysis } from '../api/types';
import { ReportSection } from './ReportSection';

/** Next month's estimate, any slab cliff ahead, and the one change that would save the most. */
export function Outlook({ analysis: a }: { analysis: Analysis }) {
  const p = a.prediction;
  return (
    <ReportSection title={`Next month, ${monthLabel(p.month)}`} caption={`Based on ${p.method}.`}>
      <Stack direction="row" sx={{ gap: { xs: 3, sm: 5 }, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>Likely units</Typography>
          <Typography sx={{ fontSize: '1.5rem', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
            {formatCount(p.units)}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Range {formatCount(p.units_low)} to {formatCount(p.units_high)}
          </Typography>
        </Box>
        <Box>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>Likely bill</Typography>
          <Typography sx={{ fontSize: '1.5rem', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{rupees(p.amount)}</Typography>
        </Box>
      </Stack>
      {p.crosses !== null && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          At this rate you may cross {formatCount(p.crosses)} units next month.
        </Alert>
      )}
      {a.cliffs.map((c) => (
        <Typography key={c.threshold} variant="body2" sx={{ mt: 1.5, color: 'text.secondary' }}>
          Going from {formatCount(c.threshold)} to {formatCount(c.threshold + 1)} units adds {rupees(c.jump)} ({rupees(c.amount_at)} becomes {rupees(c.amount_after)}).
        </Typography>
      ))}
      {a.saving && (
        <Box sx={{ mt: 2, p: 2, borderRadius: 1.5, bgcolor: 'success.light' }}>
          <Typography variant="subtitle2" sx={{ color: 'success.dark' }}>
            Use {formatCount(a.saving.cut_units)} fewer units to stay at {formatCount(a.saving.target_units)} and save {rupees(a.saving.saving)}
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            That is about {formatCount(a.saving.ac_minutes_per_day)} minutes less AC a day, or {formatCount(a.saving.geyser_minutes_per_day)} minutes less geyser.
          </Typography>
        </Box>
      )}
    </ReportSection>
  );
}

export function Explanation({ paragraphs, language }: { paragraphs: string[]; language: Language }) {
  if (paragraphs.length === 0) return null;
  return (
    <ReportSection title="In plain words">
      <Box lang={language} dir={isRtl(language) ? 'rtl' : 'ltr'} sx={{ maxWidth: '65ch' }}>
        {paragraphs.map((text, i) => (
          <Typography key={i} variant="body1" sx={{ mb: 1.5, lineHeight: 1.75 }}>
            {text}
          </Typography>
        ))}
      </Box>
    </ReportSection>
  );
}
