import { Alert, Box, FormControlLabel, Grid, Paper, Skeleton, Slider, Switch, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { ChartsReferenceLine } from '@mui/x-charts/ChartsReferenceLine';
import { LineChart } from '@mui/x-charts/LineChart';
import { useState } from 'react';

import { ErrorState } from '@/shared/components/States';
import { useDebounced } from '@/shared/hooks/useDebounced';
import { rupees } from '@/shared/lib/format';

import { useCalculation, useTariffs, type Calculation, type Cliff } from '../api/tariffApi';
import { VERIFY_LABEL } from '../model/copy';
import { BillBreakdown } from './BillBreakdown';

// The current month in India time, so the engine picks the tariff in force today.
const MONTH = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', timeZone: 'Asia/Kolkata' }).format(new Date());

interface CurveProps { data: Calculation; units: number; gruhaJyothi: boolean }

/** The cost curve, its biggest jump and what the engine still marks for confirmation. */
function CostCurve({ data, units, gruhaJyothi }: CurveProps) {
  const theme = useTheme();
  const freeLimit = useTariffs().data?.at(-1)?.gruha_jyothi_limit;
  const cliff = data.cliffs.reduce<Cliff | undefined>((a, b) => (!a || b.jump > a.jump ? b : a), undefined);
  const verify = data.computation.verify.map((v) => VERIFY_LABEL[v] ?? v);
  return (
    <>
      <LineChart
        height={300}
        dataset={data.curve}
        xAxis={[{ dataKey: 'units', label: 'Units in the month', min: 0, max: 400 }]}
        yAxis={[{ width: 64, valueFormatter: (v: number) => `Rs ${Math.round(v)}` }]}
        series={[{ dataKey: 'amount', label: 'Amount to pay', showMark: false, color: theme.palette.primary.main,
          valueFormatter: (v: number | null) => (v === null ? '' : rupees(v)) }]}
        margin={{ left: 8, right: 16, top: 16, bottom: 8 }}
      >
        <ChartsReferenceLine x={units} lineStyle={{ stroke: theme.palette.secondary.main, strokeDasharray: '4 4' }} />
      </LineChart>
      {cliff && (
        <Alert severity="warning" variant="outlined" sx={{ mt: 1 }}>
          Going from {cliff.threshold} to {cliff.threshold + 1} units adds {rupees(cliff.jump)}
          {gruhaJyothi && cliff.threshold === freeLimit
            ? ', because the free supply stops for the whole month.'
            : ', because every unit moves to a higher slab.'}
        </Alert>
      )}
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 1 }}>
        Calculated by the same rule engine the assistant uses.
        {verify.length > 0 && ` Still to confirm with the DISCOM: ${verify.join(', ')}.`}
      </Typography>
    </>
  );
}

/** Move the slider and watch the bill. The biggest cliff is the thing most households never see coming. */
export function TariffExplorer() {
  const [units, setUnits] = useState(180);
  const [gruhaJyothi, setGruhaJyothi] = useState(true);
  const settled = useDebounced(units);
  const calc = useCalculation(settled, MONTH, gruhaJyothi);
  const data = calc.data;

  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 } }}>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 5 }}>
          <Typography variant="subtitle1">Units this month: {units}</Typography>
          <Slider value={units} min={0} max={400} step={1} onChange={(_e, v) => setUnits(v)}
            marks={[{ value: 100, label: '100' }, { value: 200, label: '200' }, { value: 300, label: '300' }]}
            aria-label="Units consumed" sx={{ mt: 1 }} />
          <FormControlLabel control={<Switch checked={gruhaJyothi} onChange={(e) => setGruhaJyothi(e.target.checked)} />}
            label="Gruha Jyothi household" />
          <Box sx={{ mt: 2 }}>
            {!data && !calc.isError && <Skeleton variant="rounded" height={220} />}
            {calc.isError && <ErrorState message="Could not calculate." onRetry={() => void calc.refetch()} />}
            {data && <BillBreakdown comp={data.computation} />}
          </Box>
        </Grid>
        <Grid size={{ xs: 12, md: 7 }}>
          {data && <CostCurve data={data} units={settled} gruhaJyothi={gruhaJyothi} />}
        </Grid>
      </Grid>
    </Paper>
  );
}
