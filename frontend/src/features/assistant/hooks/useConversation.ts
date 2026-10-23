import { useCallback, useReducer, useRef, useState } from 'react';

import { billFileIssue } from '@/shared/lib/billFile';

import { mediaUrl, resetConversation, sendMessage, upload } from '../api/assistantApi';
import type { Language, OutgoingMessage, ReplyButton, StreamEvent } from '../api/types';
import { initialState, reducer, type ThreadItem, type UserContent } from '../model/conversation';
import type { ChatFailure } from '../model/failures';

const failed = (error: unknown): { type: 'failed'; error: ChatFailure } => ({ type: 'failed', error: { kind: 'request', error } });

/** Messages sent in this visit, streamed replies and the step trace for each turn. */
export function useConversation(onCleared: () => void) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [language, setLanguage] = useState<Language>('te');
  // What Try again repeats: the last thing sent, so a failed turn needs no retyping or new pick.
  const last = useRef<(() => Promise<void>) | null>(null);
  const remember = useCallback((attempt: () => Promise<void>) => {
    last.current = attempt;
    return attempt();
  }, []);

  const run = useCallback(
    async (content: UserContent, title: string, message: OutgoingMessage) => {
      dispatch({ type: 'user', content, title });
      const onEvent = (event: StreamEvent) => {
        if (event.kind === 'trace') dispatch({ type: 'trace', step: event.trace });
        else if (event.kind === 'message') dispatch({ type: 'bot', message: event.message, serverId: event.chat_id ?? undefined });
        else if (event.kind === 'state' && event.chat_id) dispatch({ type: 'stored', serverId: event.chat_id });
        else if (event.kind === 'transcript') dispatch({ type: 'transcript', text: event.text });
      };
      try {
        await sendMessage(language, message, onEvent);
        dispatch({ type: 'done' });
      } catch (error) {
        dispatch(failed(error));
      }
    },
    [language],
  );

  const sendText = useCallback(
    (text: string) => remember(() => run({ kind: 'text', text }, `Text: "${text.slice(0, 48)}"`, { kind: 'text', text })),
    [run, remember],
  );

  const sendFile = useCallback(
    (file: File) => remember(async () => {
      const issue = billFileIssue(file);
      if (issue) {
        last.current = null;
        dispatch({ type: 'failed', error: { kind: 'file', issue } });
        return;
      }
      try {
        const uploaded = await upload(file, file.name);
        const isPdf = uploaded.mime_type === 'application/pdf';
        const src = mediaUrl(uploaded.media_id);
        const content: UserContent = isPdf ? { kind: 'document', name: file.name, href: src } : { kind: 'image', src };
        await run(content, `${isPdf ? 'PDF' : 'Photo'}: ${file.name}`, {
          kind: isPdf ? 'document' : 'image',
          media_id: uploaded.media_id,
          mime_type: uploaded.mime_type,
        });
      } catch (error) {
        dispatch(failed(error));
      }
    }),
    [run, remember],
  );

  const sendVoice = useCallback(
    (blob: Blob) => remember(async () => {
      try {
        const uploaded = await upload(blob, 'voice-note.webm');
        await run({ kind: 'audio', src: mediaUrl(uploaded.media_id) }, 'Voice note', {
          kind: 'audio',
          media_id: uploaded.media_id,
          mime_type: uploaded.mime_type,
        });
      } catch (error) {
        dispatch(failed(error));
      }
    }),
    [run, remember],
  );

  const reply = useCallback(
    (button: ReplyButton) =>
      remember(() => run({ kind: 'reply', title: button.title }, `Tapped: ${button.title}`, { kind: 'button_reply', reply_id: button.id })),
    [run, remember],
  );

  /** Throws on failure so the confirm dialog can stay open and say why. */
  const reset = useCallback(async () => {
    await resetConversation();
    onCleared();
    last.current = null;
    dispatch({ type: 'reset' });
  }, [onCleared]);

  const retry = useCallback(() => {
    const again = last.current;
    if (again) void again();
  }, []);

  const append = useCallback((items: ThreadItem[]) => dispatch({ type: 'pushed', items }), []);

  return { state, language, setLanguage, sendText, sendFile, sendVoice, reply, reset, retry, append };
}

export type Conversation = ReturnType<typeof useConversation>;
