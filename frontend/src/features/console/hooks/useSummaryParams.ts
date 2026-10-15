import { DISCOMS } from '@/shared/api/types';
import { useUrlState } from '@/shared/hooks/useUrlState';

import { SUMMARY_DAYS, type SummaryFilters } from '../api/consoleApi';

export function useSummaryParams() {
  const url = useUrlState();
  const daysParam = Number(url.text('days'));
  const filters: SummaryFilters = {
    days: SUMMARY_DAYS.find((d) => d === daysParam) ?? 30,
    discom: url.pick('discom', DISCOMS),
  };
  return {
    filters,
    setDays: (days: number) => url.update({ days: days === 30 ? null : String(days) }),
    setDiscom: (discom: string) => url.update({ discom }),
  };
}
