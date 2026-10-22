import { formatCount } from '@/shared/lib/format';

import type { CaseRow, Spike } from '../api/types';
import { ratioOf } from './labels';

/** What the case is about in a few words: the flag, said plainly. */
export function headline(c: Pick<CaseRow, 'units' | 'median_units'> & { spike?: Pick<Spike, 'reason'> }): string {
  if (c.spike?.reason === 'reading_went_back') return 'Meter reading went backwards';
  if (c.units === null) return 'Reading check, units not read';
  const ratio = ratioOf(c.units, c.median_units);
  const units = `${formatCount(c.units)} units billed`;
  return ratio === null ? `${units}, no earlier months to compare` : `${units}, ${ratio.toFixed(1)}x the usual`;
}
