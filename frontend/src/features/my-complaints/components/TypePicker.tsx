import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { Accordion, AccordionDetails, AccordionSummary, Box, FormControlLabel, Radio, RadioGroup, Skeleton, Stack, Typography } from '@mui/material';
import { useState } from 'react';

import { groupTypes, useComplaintTypes, type ComplaintType } from '@/features/complaints';
import { ErrorState } from '@/shared/components/States';

interface TypePickerProps {
  value: string;
  onChange: (type: ComplaintType) => void;
  error?: boolean;
}

function Loading() {
  return (
    <Stack sx={{ gap: 1 }} aria-busy aria-label="Loading complaint types">
      {[0, 1, 2].map((i) => <Skeleton key={i} variant="rounded" height={52} />)}
    </Stack>
  );
}

/** Types grouped by category. Billing is what most people come for, so it starts open. */
export function TypePicker({ value, onChange, error = false }: TypePickerProps) {
  const types = useComplaintTypes();
  const groups = groupTypes(types.data ?? []);
  const [open, setOpen] = useState<Set<string>>(() => new Set(['billing']));
  if (types.isPending) return <Loading />;
  if (types.isError) return <ErrorState message="Could not load the list of problems. Please try again." onRetry={() => void types.refetch()} />;

  const toggle = (category: string) => setOpen((now) => {
    const next = new Set(now);
    if (next.has(category)) next.delete(category); else next.add(category);
    return next;
  });
  const byCode = new Map((types.data ?? []).map((t) => [t.code, t]));

  return (
    <RadioGroup value={value} onChange={(_e, code) => { const t = byCode.get(code); if (t) onChange(t); }} aria-label="What is the problem?">
      <Box sx={{ border: 1, borderColor: error ? 'error.main' : 'divider', borderRadius: 2, overflow: 'hidden' }}>
        {groups.map((g, i) => {
          const key = g.category.toLowerCase();
          const chosen = g.types.find((t) => t.code === value);
          return (
            <Accordion key={g.category} disableGutters square elevation={0} expanded={open.has(key)} onChange={() => toggle(key)}
              sx={{ borderTop: i ? 1 : 0, borderColor: 'divider', '&::before': { display: 'none' } }}>
              <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />} sx={{ px: 2, minHeight: 52 }}>
                <Typography variant="subtitle1" component="span" sx={{ flex: 1 }}>{g.label}</Typography>
                {chosen && !open.has(key) && (
                  <Typography variant="body2" component="span" noWrap sx={{ color: 'primary.main', mr: 1, maxWidth: '55%' }}>{chosen.label}</Typography>
                )}
              </AccordionSummary>
              <AccordionDetails sx={{ px: 2, pt: 0, pb: 1.5 }}>
                <Stack>
                  {g.types.map((t) => (
                    <FormControlLabel key={t.code} value={t.code} control={<Radio size="small" />} label={t.label}
                      sx={{ mx: 0, py: 0.25, borderRadius: 1, '&:hover': { bgcolor: 'action.hover' }, '& .MuiFormControlLabel-label': { fontSize: '0.9375rem' } }} />
                  ))}
                </Stack>
              </AccordionDetails>
            </Accordion>
          );
        })}
      </Box>
    </RadioGroup>
  );
}
