import { Alert, Box, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { BarChart } from '@mui/x-charts/BarChart';
import { ChartsReferenceLine } from '@mui/x-charts/ChartsReferenceLine';

import { formatCount, monthLabel, rupees } from '@/shared/lib/format';

import type { CaseDetail } from '../api/types';
import { ratioText } from '../model/labels';
import { Figure, Panel } from './Panel';

type Source = CaseDetail['history'][number]['source'];
const SOURCES: Source[] = ['printed', 'uploaded', 'this_bill'];
const SOURCE_LABEL: Record<Source, string> = { printed: 'Printed on the bill', uploaded: 'Earlier upload', this_bill: 'This bill' };

/** One series per source, stacked, so each bar carries one colour and the legend says where each month came from. */
function HistoryBars({ c }: { c: CaseDetail }) {
  const theme = useTheme();
  const colour: Record<Source, string> = { printed: theme.palette.chart.printed, uploaded: theme.palette.chart.uploaded, this_bill: theme.palette.chart.thisBill };
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
      <Box sx={{ display: 'grid', gap: 2, mb: 2, gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(4, minmax(0, 1fr))' } }}>
        <Figure label="This month" value={`${formatCount(s.units)} units`} />
        <Figure label="Usual month" value={s.median_units === null ? 'No history' : `${formatCount(s.median_units)} units`} />
        <Figure label="Compared with usual" value={ratioText(s.ratio) || 'Not comparable'} strong={s.ratio !== null} />
        <Figure label="A usual month costs" value={s.usual_amount === null ? 'Not known' : rupees(s.usual_amount)}
          note={c.printed_amount === null ? undefined : `Printed: ${rupees(c.printed_amount)}`} />
      </Box>
      <HistoryBars c={c} />
    </Panel>
  );
}
