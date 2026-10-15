import { Grid } from '@mui/material';

import type { Summary } from '../api/consoleApi';
import { ActivityChart } from './ActivityChart';
import { IntentBreakdown, LanguageBreakdown } from './Breakdown';
import { SectionsTable } from './SectionsTable';

/** Chart, languages, sections and questions. A window with no questions gets no questions card at all. */
export function ActivityGrid({ data }: { data: Summary | undefined }) {
  const showIntents = data === undefined || data.intents.length > 0;
  return (
    <Grid container spacing={2}>
      <Grid size={{ xs: 12, lg: 8 }}>
        <ActivityChart data={data} />
      </Grid>
      <Grid size={{ xs: 12, lg: 4 }}>
        <LanguageBreakdown rows={data?.languages} />
      </Grid>
      <Grid size={{ xs: 12, lg: showIntents ? 8 : 12 }}>
        <SectionsTable rows={data?.sections} />
      </Grid>
      {showIntents && (
        <Grid size={{ xs: 12, lg: 4 }}>
          <IntentBreakdown rows={data?.intents} />
        </Grid>
      )}
    </Grid>
  );
}
