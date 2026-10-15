import { Box, Stack, Typography, useTheme } from '@mui/material';

type Mode = 'channel' | 'ai' | 'rules' | 'staff';

const STAGES: Array<{ name: string; mode: Mode; line: string }> = [
  { name: 'Receive', mode: 'channel', line: 'Photo, PDF, voice or text, on WhatsApp or this site' },
  { name: 'Read', mode: 'ai', line: 'A first look to check it is a bill, then a careful read' },
  { name: 'Check', mode: 'rules', line: 'Rule checks on every line against the TGERC order' },
  { name: 'Explain', mode: 'ai', line: 'Plain words in the consumer\'s language, every figure guarded' },
  { name: 'Reply', mode: 'channel', line: 'Text and buttons, with a voice note when voice is on' },
  { name: 'Follow up', mode: 'staff', line: 'Complaints go to officers in the complaints inbox' },
];

const MODE_LABEL: Record<Mode, string> = { channel: 'Channel', ai: 'AI', rules: 'Rules', staff: 'Staff' };

/** The six things that happen to every bill, coloured by who does the work. */
export function PipelineStrip() {
  const { palette: p } = useTheme();
  const colour: Record<Mode, string> = { channel: p.step.channel, ai: p.step.ai, rules: p.step.rules, staff: p.primary.main };

  return (
    <Box component="ol" aria-label="What happens to a bill"
      sx={{ m: 0, p: 0, listStyle: 'none', display: 'grid', gap: 2,
        gridTemplateColumns: { xs: '1fr 1fr', sm: 'repeat(3, 1fr)', md: 'repeat(6, 1fr)' } }}>
      {STAGES.map((s) => (
        <Stack component="li" key={s.name} sx={{ gap: 0.5, pt: 1.5, borderTop: 3, borderColor: colour[s.mode], minWidth: 0 }}>
          <Typography variant="caption" sx={{ color: colour[s.mode], fontWeight: 600 }}>{MODE_LABEL[s.mode]}</Typography>
          <Typography variant="h3" component="span">{s.name}</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>{s.line}</Typography>
        </Stack>
      ))}
    </Box>
  );
}
