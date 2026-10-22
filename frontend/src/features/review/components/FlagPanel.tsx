import { Alert, Box, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { BarChart } from '@mui/x-charts/BarChart';
import { ChartsReferenceLine } from '@mui/x-charts/ChartsReferenceLine';

import { formatCount, monthLabel, rupees } from '@/shared/lib/format';

import type { CaseDetail, HistorySource } from '../api/types';
import { Panel } from './Panel';

const SOURCES: HistorySource[] = ['printed', 'uploaded', 'discom', 'this_bill'];
const SOURCE_LABEL: Record<HistorySource, string> = {
  printed: 'Printed on the bill', uploaded: 'Earlier upload', discom: 'DISCOM records', this_bill: 'This bill',
};

/** One series per source, stacked, so each bar carries one colour and the legend says where each month came from. */
function HistoryBars({ c }: { c: CaseDetail }) {
  const theme = useTheme();
  const { chart } = theme.palette;
  const colour: Record<HistorySource, string> = { printed: chart.printed, uploaded: chart.uploaded, discom: chart.discom, this_bill: chart.thisBill };
  const history = c.history;
  const median = c.spike.median_units;
  if (history.length < 2) {
    return <Typography variant="body2" sx={{ color: 'text.secondary' }}>Not enough earlier months on file to draw a trend.</Typography>;
  }
  return (
    <Box role="img" aria-label={`Units per month for ${history.length} months, this bill highlighted`}>
      <BarChart height={240}
        xAxis={[{ scaleType: 'band', data: history.map((h) => monthLabel(h.month)), tickLabelStyle: { fontSize: 11 } }]}
        yAxis={[{ width: 48, label: 'Units' }]}
        series={SOURCES.filter((s) => history.some((h) => h.source === s)).map((source) => ({
          id: source, label: SOURCE_LABEL[source], stack: 'units', color: colour[source],
          data: history.map((h) => (h.source === source ? h.units : null)),
          valueFormatter: (v: number | null, { dataIndex }: { dataIndex: number }) => {
            const amount = history[dataIndex]?.amount;
            return v === null ? null : `${formatCount(v)} units${amount === undefined ? '' : `, ${rupees(amount)}`}`;
          },
        }))}
        borderRadius={3}
        margin={{ left: 0, right: 8, top: 8, bottom: 0 }}
        slotProps={{ legend: { position: { vertical: 'top', horizontal: 'start' } } }}>
        {median !== null && (
          <ChartsReferenceLine y={median} label={`usual ${formatCount(median)}`} labelAlign="end"
            lineStyle={{ stroke: theme.palette.chart.reference, strokeDasharray: '4 4' }}
            labelStyle={{ fontSize: 11, fill: theme.palette.chart.reference }} />
        )}
      </BarChart>
    </Box>
  );
}

/** The rule-engine facts behind the flag. Every figure here comes from the server; nothing is worked out on screen. */
export function FlagPanel({ c }: { c: CaseDetail }) {
  const s = c.spike;
  const wentBack = s.reason === 'reading_went_back';
  return (
    <Panel title="Why it was flagged" tone="warning"
      caption={`Compared with the household's usual month, the median of ${s.months_used} earlier ${s.months_used === 1 ? 'month' : 'months'}.`}>
      {wentBack && (
        <Alert severity="warning" sx={{ mb: 2 }}>The present reading is lower than the previous reading. A meter does not run backwards, so one of them is wrong.</Alert>
      )}
      {!s.flagged && !wentBack && (
        <Alert severity="info" sx={{ mb: 2 }}>The engine did not flag this bill. The consumer asked for a check themselves.</Alert>
      )}
      <HistoryBars c={c} />
    </Panel>
  );
}
