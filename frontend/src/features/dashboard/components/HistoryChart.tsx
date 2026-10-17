import { Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { BarChart } from '@mui/x-charts/BarChart';
import { ChartsReferenceLine } from '@mui/x-charts/ChartsReferenceLine';

import { formatCount, monthLabel, rupees } from '@/shared/lib/format';

import { useSubsidyLimit } from '../api/billsApi';
import type { Analysis, HistorySource } from '../api/types';
import { HISTORY_SOURCE } from '../model/labels';
import { ReportSection } from './ReportSection';

const SOURCES: HistorySource[] = ['printed', 'uploaded', 'discom', 'this_bill'];

/** Units per month. One series per source, stacked, so each bar carries exactly one colour and one legend entry. */
export function HistoryChart({ history, tariffId }: { history: Analysis['history']; tariffId: string }) {
  const theme = useTheme();
  const limit = useSubsidyLimit(tariffId).data ?? null;
  const colours: Record<HistorySource, string> = {
    printed: theme.palette.chart.printed,
    uploaded: theme.palette.chart.uploaded,
    discom: theme.palette.chart.discom,
    this_bill: theme.palette.chart.thisBill,
  };
  const caption = history.some((h) => h.source === 'discom')
    ? 'From the usage table printed on this bill, your own earlier uploads and DISCOM billing records'
    : 'From the usage table printed on this bill and your own earlier uploads';

  if (history.length < 2) {
    return (
      <ReportSection title="Usage over time" caption={caption}>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          A trend needs at least two months. If your bill does not print past usage, upload last month&apos;s bill too.
        </Typography>
      </ReportSection>
    );
  }

  const present = SOURCES.filter((s) => history.some((h) => h.source === s));
  const amountFor = (index: number) => history[index]?.amount;
  return (
    <ReportSection title="Usage over time" caption={caption}>
      <BarChart
        height={260}
        xAxis={[{ scaleType: 'band', data: history.map((h) => monthLabel(h.month)), tickLabelStyle: { fontSize: 11 } }]}
        yAxis={[{ width: 44, label: 'Units' }]}
        series={present.map((source) => ({
          id: source,
          label: HISTORY_SOURCE[source],
          stack: 'units',
          color: colours[source],
          data: history.map((h) => (h.source === source ? h.units : null)),
          valueFormatter: (v: number | null, { dataIndex }: { dataIndex: number }) => {
            const amount = amountFor(dataIndex);
            return v === null ? null : `${formatCount(v)} units${amount === undefined ? '' : `, ${rupees(amount)}`}`;
          },
        }))}
        borderRadius={3}
        margin={{ left: 0, right: 8, top: 8, bottom: 0 }}
        slotProps={{ legend: { position: { vertical: 'top', horizontal: 'start' } } }}
      >
        {limit !== null && (
          <ChartsReferenceLine y={limit} label={`${formatCount(limit)} units`} labelAlign="end"
            lineStyle={{ stroke: theme.palette.chart.reference, strokeDasharray: '4 4' }}
            labelStyle={{ fontSize: 11, fill: theme.palette.chart.reference }} />
        )}
      </BarChart>
      {limit !== null && (
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          Above {formatCount(limit)} units a month, every unit moves to a higher slab and Gruha Jyothi stops for that month.
        </Typography>
      )}
    </ReportSection>
  );
}
