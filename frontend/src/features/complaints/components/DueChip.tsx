import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import { Chip } from '@mui/material';
import { useState } from 'react';

import { daysSince, parseUtc, shortDate } from '@/shared/lib/format';

import type { ComplaintRow } from '../api/types';

const OPEN = new Set(['Open', 'In progress']);
const HOUR = 3_600_000;

/** When the reply is due, or how late it is. The server decides overdue; the date is only shown. */
export function DueChip({ c, size = 'small' }: { c: Pick<ComplaintRow, 'status' | 'overdue' | 'due_at' | 'days_open'>; size?: 'small' | 'medium' }) {
  // Read once on mount: the list refreshes on its own, which is soon enough for a due today tint.
  const [now] = useState(Date.now);
  if (!OPEN.has(c.status)) return null;
  if (c.overdue) {
    const late = c.due_at ? daysSince(c.due_at) : null;
    const label = late ? `Overdue by ${late} ${late === 1 ? 'day' : 'days'}` : `Overdue, ${c.days_open} days open`;
    return <Chip size={size} color="error" icon={<ScheduleRoundedIcon />} label={label} />;
  }
  if (!c.due_at) return null;
  const soon = parseUtc(c.due_at).getTime() - now < 24 * HOUR;
  return <Chip size={size} variant="outlined" color={soon ? 'warning' : 'default'} icon={<ScheduleRoundedIcon />} label={`Due ${shortDate(c.due_at)}`} />;
}

export function DemoChip({ size = 'small' }: { size?: 'small' | 'medium' }) {
  return <Chip size={size} variant="outlined" color="info" label="Demo" title="Sample data for training and demos, not a real consumer" />;
}
