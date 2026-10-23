import { Box } from '@mui/material';
import { useMemo } from 'react';

import { ApiError } from '@/shared/api/http';

import type { Language, ReplyButton } from '../api/types';
import type { History } from '../hooks/useHistory';
import { useThreadScroll } from '../hooks/useThreadScroll';
import type { ThreadItem } from '../model/conversation';
import { FAILURE_TEXT, failureLine, type ChatFailure } from '../model/failures';
import { UI } from '../model/strings';
import { buildRows } from '../model/thread';
import { BotMessage } from './BotMessage';
import { FailureLine } from './FailureLine';
import { DayChip, JumpToLatest, LoadEarlier, SavedNotice, ThreadSkeleton, TypingBubble } from './ThreadParts';
import { UserMessage } from './UserMessage';
import { WelcomeCard } from './WelcomeCard';

interface ChatThreadProps {
  items: ThreadItem[];
  history: History;
  busy: boolean;
  error: ChatFailure | null;
  language: Language;
  onReply: (button: ReplyButton) => void;
  onRetry: () => void;
  onAttach: () => void;
  onText: (text: string) => void;
}

function Messages({ items, busy, onReply }: Pick<ChatThreadProps, 'items' | 'busy' | 'onReply'>) {
  const rows = useMemo(() => buildRows(items, new Date()), [items]);
  const lastUser = items.findLastIndex((item) => item.from === 'user');
  // Only a voice reply that arrives in this visit plays by itself; saved ones wait for a tap.
  const autoPlayKey = items.findLast((item) => item.live && item.from === 'bot' && item.message.type === 'audio')?.key;
  const pendingKey = busy ? items[lastUser]?.key : undefined;

  return rows.map((row) => {
    if (row.kind === 'day') return <DayChip key={row.key} label={row.label} />;
    const { item, first } = row;
    return item.from === 'user' ? (
      <UserMessage key={row.key} content={item.content} at={item.at} first={first} live={item.live}
        ticks={item.key === pendingKey ? 'sent' : 'read'} />
    ) : (
      <BotMessage key={row.key} message={item.message} at={item.at} first={first} live={item.live}
        autoPlay={item.key === autoPlayKey} disabled={busy} onReply={onReply} />
    );
  });
}

function Wallpaper() {
  return (
    <Box aria-hidden
      sx={(theme) => {
        const ink = theme.palette.chat.pattern;
        return {
          position: 'absolute', inset: 0, pointerEvents: 'none', bgcolor: theme.palette.chat.wallpaper,
          // A quiet lattice of rings and dots, drawn with gradients so there is no image to load.
          backgroundImage: [
            `radial-gradient(circle at 12px 12px, transparent 5px, ${ink} 5.5px, ${ink} 6.5px, transparent 7px)`,
            `radial-gradient(circle at 36px 36px, ${ink} 1.5px, transparent 2px)`,
            `radial-gradient(circle at 36px 12px, ${ink} 1px, transparent 1.5px)`,
          ].join(', '),
          backgroundSize: '48px 48px',
        };
      }} />
  );
}

function TurnFailure({ error, language, onRetry }: { error: ChatFailure; language: Language; onRetry: () => void }) {
  const { text, ref } = failureLine(error, language);
  // A refused file needs a different file, not the same one again.
  return <FailureLine text={text} reference={ref} language={language} onRetry={error.kind === 'request' ? onRetry : undefined} />;
}

function HistoryFailure({ history, language }: { history: History; language: Language }) {
  if (!history.error) return null;
  return (
    <FailureLine text={FAILURE_TEXT[language].history} language={language} onRetry={history.retry}
      reference={history.error instanceof ApiError ? history.error.ref : null} />
  );
}

export function ChatThread({ items, history, busy, error, language, onReply, onRetry, onAttach, onText }: ChatThreadProps) {
  const empty = !history.loading && !history.error && items.length === 0 && !busy;
  const { box, content, onScroll, atBottom, unread, jumpToLatest, holdPosition } = useThreadScroll(items);
  const loadEarlier = () => {
    holdPosition();
    history.loadEarlier();
  };

  return (
    <Box sx={{ position: 'relative', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      <Wallpaper />
      <Box ref={box} onScroll={onScroll} role="log" aria-label="Chat with Bill Mitra" aria-live="polite" tabIndex={0}
        sx={{ position: 'relative', flex: 1, overflowY: 'auto', overscrollBehavior: 'contain', outline: 'none',
          '&:focus-visible': { boxShadow: (t) => `inset 0 0 0 2px ${t.palette.primary.main}` } }}>
        <Box ref={content} sx={{ pb: 1.5 }}>
          {history.hasEarlier ? (
            <LoadEarlier loading={history.loadingEarlier} failed={history.earlierFailed} onLoad={loadEarlier} />
          ) : (
            !history.loading && <SavedNotice />
          )}
          {history.loading && <ThreadSkeleton />}
          <HistoryFailure history={history} language={language} />
          {empty && <WelcomeCard language={language} busy={busy} onAttach={onAttach} onText={onText} />}
          <Messages items={items} busy={busy} onReply={onReply} />
          {busy && <TypingBubble label={UI[language].typing} />}
          {error && <TurnFailure error={error} language={language} onRetry={onRetry} />}
        </Box>
      </Box>
      {!atBottom && <JumpToLatest unread={unread} onJump={jumpToLatest} />}
    </Box>
  );
}
