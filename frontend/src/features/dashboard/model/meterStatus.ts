/**
 * The two digit "Sts" beside each reading on a spot bill. Only 01 is a reading taken from the meter.
 * Meanings follow the backend (app/domain/meter_status.py) and are pending DISCOM confirmation.
 */
const MEANING: Record<string, string> = {
  '01': 'Read from the meter',
  '02': 'Meter stuck, units estimated',
  '04': 'Meter changed, units partly estimated',
  '05': 'Door locked, units estimated',
  '09': 'Marked not in use, units estimated',
};

export function statusMeaning(code: string): string {
  return MEANING[code] ?? 'Unusual status, units may be estimated';
}

export const isEstimated = (code: string | null | undefined): code is string => Boolean(code) && code !== '01';
