import PictureAsPdfOutlinedIcon from '@mui/icons-material/PictureAsPdfOutlined';
import { Box, Stack, Typography } from '@mui/material';

import type { UserContent } from '../model/conversation';
import { Bubble, type Ticks } from './Bubble';
import { MessageImage } from './MessageImage';
import { VoiceNote } from './VoiceNote';
import { WaText } from './WaText';

interface UserMessageProps {
  content: UserContent;
  at: Date;
  first: boolean;
  live: boolean;
  ticks: Ticks;
}

function Document({ name, href }: { name: string; href?: string | undefined }) {
  const link = href ? { component: 'a' as const, href, target: '_blank', rel: 'noopener noreferrer' } : {};
  return (
    <Stack direction="row" {...link}
      sx={{ gap: 1.25, alignItems: 'center', p: 1, minWidth: 220, borderRadius: '8px', bgcolor: 'action.hover', color: 'inherit', textDecoration: 'none' }}>
      <Box sx={{ display: 'grid', placeItems: 'center', width: 36, height: 40, borderRadius: 1, bgcolor: 'error.light', color: 'error.main' }}>
        <PictureAsPdfOutlinedIcon fontSize="small" />
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }} noWrap>{name}</Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>PDF</Typography>
      </Box>
    </Stack>
  );
}

function Content({ content }: { content: UserContent }) {
  switch (content.kind) {
    case 'text':
      return <WaText text={content.text} />;
    case 'reply':
      return <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.875rem' }}>{content.title}</Typography>;
    case 'image':
      return (
        <>
          <MessageImage src={content.src} alt="Bill photo you sent" width={220} />
          {content.caption && <Box sx={{ px: 0.75, pt: 0.5 }}><WaText text={content.caption} /></Box>}
        </>
      );
    case 'document':
      return <Document name={content.name} href={content.href} />;
    case 'audio':
      return (
        <>
          <VoiceNote sources={[content.src]} />
          {content.transcript && (
            <Typography variant="body2" dir="auto" sx={{ color: 'text.secondary', fontStyle: 'italic', mt: 0.5, maxWidth: 260 }}>
              {content.transcript}
            </Typography>
          )}
        </>
      );
    default:
      return null;
  }
}

export function UserMessage({ content, at, first, live, ticks }: UserMessageProps) {
  return (
    <Bubble side="out" at={at} first={first} animate={live} ticks={ticks} flush={content.kind === 'image' || content.kind === 'document'}>
      <Content content={content} />
    </Bubble>
  );
}
