import { Paper, Skeleton, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { BarChart } from '@mui/x-charts/BarChart';

import { shortDate } from '@/shared/lib/format';

import type { Summary } from '../api/consoleApi';

type Day = Summary['daily'][number];

const todayInIndia = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'Asia/Kolkata' });

/** The API only sends days with activity (as India dates); fill the rest of the window with zeros so gaps read as quiet days. */
function fillWindow(daily: Day[], days: number): Day[] {
  const byDate = new Map(daily.map((d) => [d.date, d]));
  const end = new Date(`${todayInIndia.format(new Date())}T00:00:00Z`).getTime();
  return Array.from({ length: days }, (_, i) => {
    const date = new Date(end - (days - 1 - i) * 86_400_000).toISOString().slice(0, 10);
    return byDate.get(date) ?? { date, bills: 0, questions: 0 };
  });
}

export function ActivityChart({ data }: { data: Summary | undefined }) {
  const theme = useTheme();
  const series = data ? fillWindow(data.daily, data.days) : [];
  // About seven labels whatever the window, and thin bars stay apart instead of merging.
  const every = Math.max(1, Math.ceil(series.length / 7));
  return (
    <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
      <Typography variant="h3" component="h2">Daily activity</Typography>
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        Bills read and questions asked per day, India time
      </Typography>
      {!data ? <Skeleton variant="rounded" height={260} sx={{ mt: 1 }} /> : (
        <BarChart
          height={280}
          dataset={series}
          xAxis={[{ scaleType: 'band', dataKey: 'date', valueFormatter: (v: string) => shortDate(v),
            tickLabelInterval: (_v, i) => i % every === 0, categoryGapRatio: series.length <= 14 ? 0.5 : 0.25, barGapRatio: 0.1 }]}
          yAxis={[{ width: 32, tickMinStep: 1 }]}
          series={[
            { dataKey: 'bills', label: 'Bills', color: theme.palette.primary.main },
            { dataKey: 'questions', label: 'Questions', color: theme.palette.secondary.main },
          ]}
          margin={{ left: 0, right: 8, top: 16, bottom: 0 }}
        />
      )}
    </Paper>
  );
}
