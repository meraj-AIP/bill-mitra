import { Chip, Paper, Skeleton, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';

import { ErrorState } from '@/shared/components/States';
import { calendarDate } from '@/shared/lib/format';

import { useTariffs, type TariffVersion } from '../api/tariffApi';
import { VERIFY_LABEL } from '../model/copy';

function slabText(slabs: TariffVersion['groups'][number]['slabs']): string {
  let start = 0;
  return slabs
    .map((s) => {
      const range = s.upto === null ? `above ${start}` : `${start + 1} to ${s.upto}`;
      start = s.upto ?? start;
      return `${range}: Rs ${s.rate.toFixed(2)}`;
    })
    .join(', ');
}

export function TariffTable() {
  const tariffs = useTariffs();
  if (tariffs.isError) return <ErrorState message="Could not load tariff tables." onRetry={() => void tariffs.refetch()} />;
  const current = tariffs.data?.at(-1);
  const topLimit = Math.max(0, ...(current?.groups.map((g) => g.max_units ?? 0) ?? []));
  return (
    <Paper variant="outlined" sx={{ overflowX: 'auto' }}>
      <Stack direction="row" sx={{ p: 2, gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <Typography variant="h3" component="h3" sx={{ flex: 1 }}>
          Domestic tariff (LT-I) in the engine
        </Typography>
        {tariffs.data?.map((t) => <Chip key={t.id} size="small" variant="outlined" label={`${t.order} from ${calendarDate(t.effective_from)}`} />)}
      </Stack>
      {!current ? (
        <Skeleton variant="rounded" height={160} sx={{ mx: 2, mb: 2 }} />
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Group</TableCell>
              <TableCell>Applies when</TableCell>
              <TableCell>Slabs (Rs per unit)</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {current.groups.map((g) => (
              <TableRow key={g.code}>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{g.code}</TableCell>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{g.max_units === null ? `Above ${topLimit} units` : `Up to ${g.max_units} units`}</TableCell>
                <TableCell>{slabText(g.slabs)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {current && (
        <Typography variant="caption" sx={{ display: 'block', p: 2, color: 'text.secondary' }}>
          Fixed charge Rs {current.fixed_charge_per_kw} per kW. Duty {current.duty_per_unit * 100} paise per unit.
          {current.true_up && ` True-up from ${calendarDate(current.true_up.starts)}: Rs ${current.true_up.first_month_rate} per unit in the first month, Rs ${current.true_up.later_rate} after.`}
          {' '}Gruha Jyothi: zero bill up to {current.gruha_jyothi_limit} units. To confirm with the DISCOM: {current.verify.map((v) => VERIFY_LABEL[v] ?? v).join(', ')}.
        </Typography>
      )}
    </Paper>
  );
}
