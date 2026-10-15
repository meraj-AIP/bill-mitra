import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { getJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';

export interface SlabLine {
  start: number;
  end: number;
  units: number;
  rate: number;
  amount: number;
}

export interface Computation {
  tariff_id: string;
  tariff_order: string;
  group: string;
  units: number;
  slab_lines: SlabLine[];
  energy: number;
  fixed: number;
  customer: number;
  duty: number;
  fsa: number;
  gross: number;
  subsidy: number;
  net: number;
  gruha_jyothi_applied: boolean;
  verify: string[];
}

export interface Cliff {
  threshold: number;
  amount_at: number;
  amount_after: number;
  jump: number;
}

export interface Calculation {
  computation: Computation;
  curve: Array<{ units: number; amount: number }>;
  cliffs: Cliff[];
}

export interface TariffVersion {
  id: string;
  order: string;
  effective_from: string;
  effective_to: string | null;
  groups: Array<{ code: string; max_units: number | null; slabs: Array<{ upto: number | null; rate: number }> }>;
  customer_charges: Array<{ upto: number | null; amount: number }>;
  fixed_charge_per_kw: number;
  duty_per_unit: number;
  true_up: { starts: string; first_month_rate: number; later_rate: number } | null;
  gruha_jyothi_limit: number;
  verify: string[];
}

export function useTariffs() {
  return useQuery({
    queryKey: queryKeys.tariffs,
    queryFn: ({ signal }) => getJson<TariffVersion[]>('/api/tariffs', signal),
    staleTime: Infinity,
  });
}

export function useCalculation(units: number, month: string, gruhaJyothi: boolean) {
  return useQuery({
    queryKey: queryKeys.calculate(units, month, gruhaJyothi),
    queryFn: ({ signal }) =>
      getJson<Calculation>(
        `/api/tariffs/calculate?units=${units}&month=${month}&gruha_jyothi=${gruhaJyothi}&load_kw=2`,
        signal,
      ),
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  });
}
