import { calendarDate, formatCount, rupees } from '@/shared/lib/format';

const DATES = new Set(['bill_date', 'due_date', 'previous_reading_date']);
const MONEY = new Set(['energy', 'fixed', 'customer', 'duty', 'bill_amount', 'total_payable']);

/** The capture report sends every value as text ("518.20", "2025-10-19"); show each the way the rest of the report does. */
export function captureValue(key: string, value: string): string {
  if (DATES.has(key)) return calendarDate(value);
  const n = Number(value);
  if (value.trim() === '' || !Number.isFinite(n)) return value;
  if (MONEY.has(key)) return rupees(n);
  if (key === 'load_kw') return `${String(n)} kW`;
  if (key === 'billing_days') return n === 1 ? '1 day' : `${formatCount(n)} days`;
  // Meter readings and units read best exactly as printed, without grouping commas.
  return String(n);
}
