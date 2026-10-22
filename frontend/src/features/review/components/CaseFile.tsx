import { Box, Paper, Stack, Tab, Tabs, Typography } from '@mui/material';
import { useState } from 'react';

import { BillImage } from '@/shared/components/BillImage';

import type { CaseDetail } from '../api/types';
import { DecisionHistory } from './DecisionHistory';
import { EvidencePackPanel } from './EvidencePackPanel';
import { FlagPanel } from './FlagPanel';
import { ReadingsPanel } from './ReadingsPanel';
import { TimelinePanel } from './TimelinePanel';

type Section = 'flag' | 'bill' | 'decisions' | 'timeline' | 'pack';

function BillAndCharges({ c }: { c: CaseDetail }) {
  return (
    <Box sx={{ display: 'grid', gap: 2, alignItems: 'start', gridTemplateColumns: { xs: 'minmax(0, 1fr)', lg: c.media_url ? 'minmax(0, 5fr) minmax(0, 7fr)' : 'minmax(0, 1fr)' } }}>
      {c.media_url
        ? <BillImage src={c.media_url} isPdf={c.mime_type === 'application/pdf'} heading="Bill as uploaded" name={`Bill for ${c.ticket}`} />
        : (
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>No bill photo is stored for this case.</Typography>
          </Paper>
        )}
      <ReadingsPanel c={c} />
    </Box>
  );
}

/** The record behind the decision, one section at a time: why it was flagged first, then the bill with its readings
 * and charges, the decisions, the timeline and the evidence pack. */
export function CaseFile({ c }: { c: CaseDetail }) {
  const [section, setSection] = useState<Section>('flag');
  const decisions = c.decisions.length;
  return (
    <Stack sx={{ gap: 1.5, minWidth: 0 }}>
      <Paper variant="outlined" sx={{ px: 1 }}>
        <Tabs value={section} onChange={(_, v: Section) => setSection(v)} variant="scrollable" scrollButtons={false} aria-label="Case file"
          sx={{ minHeight: 44, '& .MuiTab-root': { minHeight: 44, px: 1.5 } }}>
          <Tab value="flag" label="Why it was flagged" />
          <Tab value="bill" label="Bill and charges" />
          <Tab value="decisions" label={decisions ? `Decisions (${decisions})` : 'Decisions'} />
          <Tab value="timeline" label="Timeline" />
          <Tab value="pack" label="Evidence pack" />
        </Tabs>
      </Paper>
      <Box role="tabpanel" aria-label={section}>
        {section === 'flag' && <FlagPanel c={c} />}
        {section === 'bill' && <BillAndCharges c={c} />}
        {section === 'decisions' && <DecisionHistory c={c} />}
        {section === 'timeline' && <TimelinePanel c={c} />}
        {section === 'pack' && <EvidencePackPanel c={c} />}
      </Box>
    </Stack>
  );
}
