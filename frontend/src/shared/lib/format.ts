const inr = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const count = new Intl.NumberFormat('en-IN');
const monthName = new Intl.DateTimeFormat('en-IN', { month: 'short', year: 'numeric', timeZone: 'UTC' });
// Bills, tickets and officers are all in Telangana, so times read in India time wherever the browser is.
const IST = 'Asia/Kolkata';
const dayMonthYear = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });

export function rupees(value: number): string {
  return `Rs ${Number.isInteger(value) ? inr.format(value) : inr2.format(value)}`;
}

export function formatCount(value: number): string {
  return count.format(value);
}

/** The API sends UTC timestamps, sometimes without a zone suffix. */
function parseUtc(iso: string): Date {
  const text = iso.replace(' ', 'T');
  return new Date(/[zZ]$|[+-]\d\d:?\d\d$/.test(text) ? text : `${text}Z`);
}

export function shortDate(iso: string): string {
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', timeZone: IST });
}

export function dateTime(iso: string): string {
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: IST });
}

/** A date printed on a bill ("2025-10-19") as "19 Oct 2025". It has no time, so no zone shift applies. */
export function calendarDate(ymd: string | null | undefined): string {
  if (!ymd) return 'Not printed';
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(ymd);
  if (!match) return ymd;
  return dayMonthYear.format(new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]))));
}

/** "2026-10" to "Oct 2026". Anything else is shown as given. */
export function monthLabel(month: string | null | undefined): string {
  if (!month) return 'Unknown month';
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  if (!match) return month;
  return monthName.format(new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, 1)));
}

export function clockTime(date: Date): string {
  return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: IST });
}

/** Whole days from an API timestamp to now. */
export function daysSince(iso: string, now: Date = new Date()): number {
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return 0;
  return Math.max(0, Math.floor((now.getTime() - d.getTime()) / 86_400_000));
}
