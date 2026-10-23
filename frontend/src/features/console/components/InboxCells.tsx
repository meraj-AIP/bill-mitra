import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import { Box, Link as MuiLink, Stack, Typography } from '@mui/material';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { CHANNEL_LABEL, PRIORITY, SOURCE_LABEL, TRIAGE, type ComplaintRow } from '@/features/complaints';
import { daysSince, parseUtc, rupees, shortDate } from '@/shared/lib/format';

// The list is read as text. Colour is kept for what needs someone today: late, urgent, a reply that did not arrive.
const DOT: Record<ComplaintRow['status'], string> = { Open: 'text.disabled', 'In progress': 'primary.main', Resolved: 'success.main', Rejected: 'text.disabled' };
const OPEN = new Set(['Open', 'In progress']);
const HOUR = 3_600_000;
const CLAMP = { display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' } as const;

export function complaintPath(ticket: string): string {
  return `/console/complaints/${encodeURIComponent(ticket)}`;
}

function source(c: ComplaintRow): string {
  if (c.source) return SOURCE_LABEL[c.source];
  return c.channel ? CHANNEL_LABEL[c.channel] : 'Unknown';
}

/** The consumer's words. A complaint logged from a type often starts with the type's own title; it is already the
 * line above, so it is not said twice. */
function words(c: ComplaintRow): string {
  const title = c.type_label?.trim();
  const issue = c.issue.trim();
  const rest = title && issue.toLowerCase().startsWith(title.toLowerCase()) ? issue.slice(title.length).replace(/^[\s.:,-]+/, '') : issue;
  return `${c.amount ? `${rupees(c.amount)}. ` : ''}${rest || issue}`;
}

/** What it is about, the consumer's words, then where it came from in one quiet line. */
export function ComplaintCell({ c }: { c: ComplaintRow }) {
  const meta = [source(c), c.discom, shortDate(c.created_at)].filter(Boolean).join(' · ');
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="subtitle2" component="p" sx={CLAMP}>{c.type_label ?? 'Complaint'}</Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', ...CLAMP }}>{words(c)}</Typography>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 0.25 }}>
        <MuiLink component={Link} to={complaintPath(c.ticket)} onClick={(e) => e.stopPropagation()} color="inherit"
          underline="hover" sx={{ fontFamily: 'monospace', fontWeight: 600, color: 'text.primary' }}>
          {c.ticket}
        </MuiLink>
        {` · ${meta}`}{c.demo ? ' · Demo' : ''}
      </Typography>
    </Box>
  );
}

/** The status as a word, with whose move it is, and at most one flag that needs attention. */
export function StatusCell({ c }: { c: ComplaintRow }) {
  const holder = c.waiting_on === 'consumer' ? 'Waiting on consumer' : c.assignee_name ? `With ${c.assignee_name}` : 'Not with anyone';
  const flag = c.delivery_failed ? { text: 'Reply not delivered', color: 'error.main' }
    : c.triage === 'overcharge' ? { text: TRIAGE.overcharge.label, color: 'warning.dark' } : null;
  return (
    <Box>
      <Stack direction="row" sx={{ gap: 0.75, alignItems: 'center' }}>
        <Box aria-hidden sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: DOT[c.status], flexShrink: 0 }} />
        <Typography variant="body2" sx={{ fontWeight: 500 }}>{c.status}</Typography>
      </Stack>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary', pl: 1.75 }} noWrap>{holder}</Typography>
      {flag && <Typography variant="caption" component="p" sx={{ color: flag.color, fontWeight: 600, pl: 1.75 }}>{flag.text}</Typography>}
    </Box>
  );
}

export function PriorityCell({ c }: { c: ComplaintRow }) {
  if (!c.priority) return <Typography variant="body2" sx={{ color: 'text.disabled' }}>None</Typography>;
  const urgent = c.priority === 'urgent';
  const quiet = c.priority === 'normal' || c.priority === 'low';
  return (
    <Typography variant="body2" sx={{ fontWeight: quiet ? 400 : 600, color: urgent ? 'error.main' : quiet ? 'text.secondary' : 'text.primary' }}>
      {PRIORITY[c.priority].label}
    </Typography>
  );
}

/** When the reply is due. The server decides overdue; only the date is worked out here. */
export function DueCell({ c }: { c: ComplaintRow }) {
  // Read once on mount: the list refreshes on its own, which is soon enough for "due today".
  const [now] = useState(Date.now);
  if (!OPEN.has(c.status)) return <Typography variant="body2" sx={{ color: 'text.disabled' }}>Closed</Typography>;
  if (c.overdue) {
    const late = c.due_at ? daysSince(c.due_at) : null;
    return (
      <Stack direction="row" sx={{ gap: 0.5, alignItems: 'center', color: 'error.main' }}>
        <ScheduleRoundedIcon sx={{ fontSize: 16 }} aria-hidden />
        <Typography variant="body2" sx={{ fontWeight: 600 }} noWrap>{late ? `${late} ${late === 1 ? 'day' : 'days'} late` : 'Overdue'}</Typography>
      </Stack>
    );
  }
  if (!c.due_at) return <Typography variant="body2" sx={{ color: 'text.disabled' }}>No due date</Typography>;
  const soon = parseUtc(c.due_at).getTime() - now < 24 * HOUR;
  return (
    <Typography variant="body2" sx={{ color: soon ? 'warning.dark' : 'text.secondary', fontWeight: soon ? 600 : 400 }} noWrap>
      {soon ? 'Due today' : `Due ${shortDate(c.due_at)}`}
    </Typography>
  );
}
