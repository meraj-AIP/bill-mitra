import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import SendOutlinedIcon from '@mui/icons-material/SendOutlined';
import { Box, Button, CircularProgress, Paper, Skeleton, Stack, Typography } from '@mui/material';
import { useId, useState } from 'react';

import { ErrorState } from './States';

export interface AssistQuestion { text: string; why: string }

export interface AssistView {
  summary: string;
  /** Short lists such as what is still missing, each with what to say when empty. */
  lists: Array<{ title: string; items: string[]; empty: string }>;
  questions: AssistQuestion[];
  /** The suggested next step as something the button does. Null when the rules offer nothing. */
  action: { label: string; why: string; run: () => void; pending?: boolean; error?: string | null } | null;
  wordedBy: 'ai' | 'rules';
}

interface AssistCardProps {
  /** What the assistant reads, as in "Reads this complaint". */
  subject: string;
  view: AssistView | null;
  pending: boolean;
  error: string | null;
  onAsk: () => void;
  /** Sends one question to the consumer as a request. Null when this account cannot ask. */
  onSendQuestion: ((text: string) => Promise<unknown>) | null;
}

const WORDED = {
  ai: 'Worded by AI from the facts on file. Any number in it was checked against those facts.',
  rules: 'Put together by the rules from the facts on file. AI wording was not used this time.',
} as const;

function Lead({ subject }: { subject: string }) {
  return (
    <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: '60ch' }}>
      Reads {subject} and the consumer&apos;s messages, then suggests what to ask and what to do next. It never works out
      an amount. Nothing is sent until you press a button.
    </Typography>
  );
}

function Loading() {
  return (
    <Stack sx={{ gap: 1 }} aria-busy aria-label="AI assist is reading">
      <Skeleton width="92%" /><Skeleton width="85%" /><Skeleton width="60%" />
      <Skeleton variant="rounded" height={64} sx={{ mt: 1 }} />
    </Stack>
  );
}

type SendState = { state: 'idle' | 'sending' | 'sent' } | { state: 'failed'; message: string };

const SEND_BUTTON = {
  idle: { label: 'Send this question', icon: <SendOutlinedIcon /> },
  failed: { label: 'Send this question', icon: <SendOutlinedIcon /> },
  sending: { label: 'Sending', icon: <CircularProgress size={14} color="inherit" aria-hidden /> },
  sent: { label: 'Sent', icon: <CheckRoundedIcon /> },
};

function sendNote(send: SendState): string {
  if (send.state === 'failed') return send.message;
  return send.state === 'sent' ? 'Asked. Their answer will show in the conversation.' : '';
}

function SendQuestion({ text, onSend }: { text: string; onSend: (text: string) => Promise<unknown> }) {
  const [send, setSend] = useState<SendState>({ state: 'idle' });
  const run = async () => {
    setSend({ state: 'sending' });
    try {
      await onSend(text);
      setSend({ state: 'sent' });
    } catch (error) {
      setSend({ state: 'failed', message: error instanceof Error ? error.message : 'The question was not sent. Try again.' });
    }
  };
  const button = SEND_BUTTON[send.state];
  return (
    <Stack direction="row" sx={{ mt: 1, gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
      <Button size="small" variant="outlined" onClick={() => void run()} disabled={send.state === 'sent' || send.state === 'sending'}
        startIcon={button.icon}>
        {button.label}
      </Button>
      <Typography variant="caption" aria-live="polite" sx={{ color: send.state === 'failed' ? 'error.main' : 'text.secondary' }}>
        {sendNote(send)}
      </Typography>
    </Stack>
  );
}

function Question({ q, onSend }: { q: AssistQuestion; onSend: ((text: string) => Promise<unknown>) | null }) {
  return (
    <Box component="li" sx={{ p: 1.5, borderRadius: 1, bgcolor: 'grey.50', border: 1, borderColor: 'divider' }}>
      <Typography variant="body2" dir="auto" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{q.text}</Typography>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 0.5 }}>{q.why}</Typography>
      {onSend && <SendQuestion text={q.text} onSend={onSend} />}
    </Box>
  );
}

function Heading({ children }: { children: string }) {
  return <Typography variant="subtitle2" component="h3" sx={{ mb: 0.75 }}>{children}</Typography>;
}

function Result({ view, onSendQuestion }: { view: AssistView; onSendQuestion: AssistCardProps['onSendQuestion'] }) {
  return (
    <Stack sx={{ gap: 2.25 }}>
      <Typography variant="body1" sx={{ whiteSpace: 'pre-line', maxWidth: '65ch' }}>{view.summary}</Typography>
      {view.lists.map((list) => (
        <Box key={list.title}>
          <Heading>{list.title}</Heading>
          {list.items.length === 0 ? (
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>{list.empty}</Typography>
          ) : (
            <Box component="ul" sx={{ m: 0, pl: 2.5, display: 'grid', gap: 0.5 }}>
              {list.items.map((item) => <Typography key={item} component="li" variant="body2">{item}</Typography>)}
            </Box>
          )}
        </Box>
      ))}
      {view.questions.length > 0 && (
        <Box>
          <Heading>Questions for the consumer</Heading>
          <Stack component="ul" sx={{ listStyle: 'none', m: 0, p: 0, gap: 1 }}>
            {view.questions.map((q) => <Question key={q.text} q={q} onSend={onSendQuestion} />)}
          </Stack>
        </Box>
      )}
      {view.action && (
        <Box sx={{ p: 1.5, borderRadius: 1, border: 1, borderColor: 'primary.main', bgcolor: 'action.hover' }}>
          <Heading>Suggested next step</Heading>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.25 }}>{view.action.why}</Typography>
          <Button variant="contained" onClick={view.action.run} disabled={view.action.pending ?? false}
            startIcon={view.action.pending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
            {view.action.label}
          </Button>
          {view.action.error && <Typography variant="caption" component="p" role="alert" sx={{ color: 'error.main', mt: 0.75 }}>{view.action.error}</Typography>}
        </Box>
      )}
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>{WORDED[view.wordedBy]}</Typography>
    </Stack>
  );
}

function Body({ subject, view, pending, error, onAsk, onSendQuestion, round }: AssistCardProps & { round: number }) {
  if (pending) return <Loading />;
  if (error) return <ErrorState message={`AI assist did not answer. ${error}`} onRetry={onAsk} />;
  if (!view) return <Lead subject={subject} />;
  return <Result key={round} view={view} onSendQuestion={onSendQuestion} />;
}

/** On demand only: nothing is asked of the model until someone presses Ask AI. */
export function AssistCard({ subject, view, pending, error, onAsk, onSendQuestion }: AssistCardProps) {
  const titleId = useId();
  const [round, setRound] = useState(0);
  const ask = () => { setRound((r) => r + 1); onAsk(); };
  return (
    <Paper component="section" variant="outlined" aria-labelledby={titleId} aria-busy={pending}
      sx={{ overflow: 'hidden', borderTop: 3, borderTopColor: 'info.main' }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ px: { xs: 2, sm: 2.5 }, pt: 2, gap: 1.5, alignItems: { sm: 'flex-start' } }}>
        <Stack direction="row" sx={{ flex: 1, minWidth: 0, gap: 1, alignItems: 'center' }}>
          <AutoAwesomeOutlinedIcon fontSize="small" sx={{ color: 'info.main' }} aria-hidden />
          <Typography id={titleId} variant="h3" component="h2">AI assist</Typography>
        </Stack>
        <Button variant={view ? 'outlined' : 'contained'} size="small" onClick={ask} disabled={pending} sx={{ alignSelf: { xs: 'flex-start', sm: 'center' } }}
          startIcon={pending ? <CircularProgress size={14} color="inherit" aria-hidden /> : <AutoAwesomeOutlinedIcon />}>
          {pending ? 'Reading' : view ? 'Ask again' : 'Ask AI'}
        </Button>
      </Stack>
      <Box sx={{ px: { xs: 2, sm: 2.5 }, pt: 1.5, pb: 2.5 }} aria-live="polite">
        <Body subject={subject} view={view} pending={pending} error={error} onAsk={ask} onSendQuestion={onSendQuestion} round={round} />
      </Box>
    </Paper>
  );
}
