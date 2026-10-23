import SwapHorizRoundedIcon from '@mui/icons-material/SwapHorizRounded';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import { Button, CircularProgress, Menu, MenuItem, Stack, Typography } from '@mui/material';
import { useState } from 'react';

import { useAssign, useUnmask } from '../api/reviewApi';
import type { CaseDetail } from '../api/types';
import { describeError, useConfirm } from '@/shared/feedback';

const LAYOUT = {
  inline: { direction: 'row', text: 'body2', sx: { gap: 0.5, alignItems: 'center' }, button: 'Show', indent: 0 },
  block: { direction: 'column', text: 'subtitle1', sx: { gap: 0.25, alignItems: 'flex-start' }, button: 'Show full number', indent: -0.75 },
} as const;

/** Shows the full number only after a deliberate click; the server records each view, and it is never cached.
 * `inline` fits it into a line of text. */
export function UnmaskControl({ c, inline = false }: { c: CaseDetail; inline?: boolean }) {
  const unmask = useUnmask(c.ticket);
  const shown = unmask.data?.service_number;
  const l = LAYOUT[inline ? 'inline' : 'block'];
  const confirm = useConfirm();
  const reveal = async () => {
    if (await confirm({ title: 'Show the full service number?', confirmLabel: 'Show number', tone: 'warning',
      body: 'This is the consumer\u2019s personal data. Each view is recorded in the audit log with your name.' })) unmask.mutate();
  };
  const canShow = c.can.unmask && Boolean(c.service_masked) && !shown;
  return (
    <Stack direction={l.direction} sx={l.sx}>
      <Typography variant={l.text} component="span" sx={{ fontFamily: 'monospace', letterSpacing: shown ? '0.04em' : 0 }}>
        {shown ?? c.service_masked ?? 'Not printed'}
      </Typography>
      {shown && <Typography variant="caption" sx={{ color: 'warning.dark' }}>This view was recorded in the audit log.</Typography>}
      {canShow && (
        <Button size="small" startIcon={unmask.isPending ? <CircularProgress size={14} aria-hidden /> : <VisibilityOutlinedIcon />}
          onClick={() => void reveal()} disabled={unmask.isPending} sx={{ ml: l.indent, py: 0 }}>
          {l.button}
        </Button>
      )}
      <UnmaskError error={unmask.error} />
    </Stack>
  );
}

function UnmaskError({ error }: { error: Error | null }) {
  return error ? <Typography variant="caption" sx={{ color: 'error.main' }}>{describeError(error).message}</Typography> : null;
}


/** Moving the case is occasional, so it is a small menu by the title rather than a form. */
export function ReassignControl({ c }: { c: CaseDetail }) {
  const assign = useAssign(c.ticket);
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const others = c.assignable.filter((p) => p.id !== c.assignee?.id);
  const confirm = useConfirm();
  if (!c.can.reassign) return null;
  const move = async (id: string) => {
    setAnchor(null);
    const name = others.find((p) => p.id === id)?.name ?? 'them';
    if (!(await confirm({ title: `Move this case to ${name}?`, confirmLabel: 'Move case',
      points: [`${name} is alerted and sees it in their queue.`, c.assignee ? `${c.assignee.name} no longer holds it.` : 'It leaves the division queue.'] }))) return;
    assign.mutate(id);
  };
  return (
    <>
      <Button variant="outlined" size="small" onClick={(e) => setAnchor(e.currentTarget)} disabled={others.length === 0 || assign.isPending}
        title={others.length === 0 ? 'Nobody else in scope can take this case.' : undefined} aria-haspopup="menu" aria-expanded={Boolean(anchor)}
        startIcon={assign.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : <SwapHorizRoundedIcon />} sx={{ flexShrink: 0 }}>
        Move case
      </Button>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}>
        {others.map((p) => <MenuItem key={p.id} onClick={() => void move(p.id)}>{p.name}</MenuItem>)}
      </Menu>
    </>
  );
}
