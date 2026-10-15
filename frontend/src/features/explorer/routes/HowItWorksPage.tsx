import { Box, Container, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

import { PageHeader } from '@/shared/components/PageHeader';

import { JourneyPlayer } from '../components/JourneyPlayer';
import { LiveStatus } from '../components/LiveStatus';
import { PipelineStrip } from '../components/PipelineStrip';
import { TariffExplorer } from '../components/TariffExplorer';
import { TariffTable } from '../components/TariffTable';
import { useJourney } from '../hooks/useJourney';
import { PRINCIPLES } from '../model/copy';

function Section({ title, lead, children }: { title: string; lead?: string; children: ReactNode }) {
  return (
    <Stack component="section" sx={{ gap: 2 }}>
      <Box>
        <Typography variant="h2">{title}</Typography>
        {lead && <Typography variant="body1" sx={{ color: 'text.secondary', maxWidth: '65ch', mt: 0.5 }}>{lead}</Typography>}
      </Box>
      {children}
    </Stack>
  );
}

function Principles() {
  return (
    <Box component="ol" sx={{ m: 0, p: 0, listStyle: 'none', display: 'grid', columnGap: 5, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
      {PRINCIPLES.map(([title, body]) => (
        <Box component="li" key={title} sx={{ py: 2, borderTop: 1, borderColor: 'divider' }}>
          <Typography variant="h3" component="h3">{title}</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5, maxWidth: '60ch' }}>{body}</Typography>
        </Box>
      ))}
    </Box>
  );
}

export function HowItWorksPage() {
  const journey = useJourney();
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: { xs: 5, md: 6 } }}>
        <PageHeader eyebrow="How it works" title="How Bill Mitra reads and checks a bill"
          lead="A consumer sends a photo of their electricity bill. Bill Mitra reads it, checks every line against the tariff and explains it in their language. If something is wrong, they can raise a complaint that DISCOM officers answer." />
        <PipelineStrip />
        <Principles />
        <Section title="Architecture, end to end"
          lead="One backend serves consumers on WhatsApp and the website, and staff in the console. Pick a journey and play it, or step through. The lit path is what moves at that step, with the payload it carries. Click any box for its files and job.">
          <JourneyPlayer control={journey} />
        </Section>
        <Section title="Live status" lead="What is switched on on this server right now.">
          <LiveStatus />
        </Section>
        <Section title="Tariff explorer" lead="The bill for any number of units, as the rule engine calculates it.">
          <TariffExplorer />
          <TariffTable />
        </Section>
      </Stack>
    </Container>
  );
}
