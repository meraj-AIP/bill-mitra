import type { Outbound, TraceStep } from '../api/types';
import type { ChatFailure } from './failures';

export type UserContent =
  | { kind: 'text'; text: string }
  | { kind: 'image'; src: string; caption?: string | undefined }
  | { kind: 'document'; name: string; href?: string | undefined }
  | { kind: 'audio'; src: string; transcript?: string | undefined }
  | { kind: 'reply'; title: string };

/** One message in the thread. `live` marks messages sent in this visit, which get the enter animation. */
export type ThreadItem =
  | { key: string; at: Date; live: boolean; from: 'user'; content: UserContent }
  | { key: string; at: Date; live: boolean; from: 'bot'; message: Outbound };

export interface TraceTurn {
  id: string;
  at: Date;
  title: string;
  steps: TraceStep[];
  done: boolean;
}

export interface ConversationState {
  items: ThreadItem[];
  turns: TraceTurn[];
  busy: boolean;
  error: ChatFailure | null;
}

export type Action =
  | { type: 'user'; content: UserContent; title: string }
  | { type: 'trace'; step: TraceStep }
  | { type: 'bot'; message: Outbound }
  | { type: 'transcript'; text: string }
  | { type: 'done' }
  | { type: 'failed'; error: ChatFailure }
  | { type: 'reset' };

export const initialState: ConversationState = { items: [], turns: [], busy: false, error: null };

let counter = 0;
const nextId = (prefix: string) => `${prefix}${Date.now().toString(36)}${(counter++).toString(36)}`;

function updateLastTurn(turns: TraceTurn[], update: (turn: TraceTurn) => TraceTurn): TraceTurn[] {
  const last = turns.at(-1);
  return last ? [...turns.slice(0, -1), update(last)] : turns;
}

function mergeStep(steps: TraceStep[], step: TraceStep): TraceStep[] {
  const index = steps.findIndex((s) => s.id === step.id);
  if (index < 0) return [...steps, step];
  return steps.map((s, i) => (i === index ? step : s));
}

function attachTranscript(items: ThreadItem[], text: string): ThreadItem[] {
  const index = items.findLastIndex((item) => item.from === 'user' && item.content.kind === 'audio');
  const item = items[index];
  if (!item || item.from !== 'user' || item.content.kind !== 'audio') return items;
  const updated: ThreadItem = { ...item, content: { ...item.content, transcript: text } };
  return [...items.slice(0, index), updated, ...items.slice(index + 1)];
}

export function reducer(state: ConversationState, action: Action): ConversationState {
  const now = new Date();
  switch (action.type) {
    case 'user':
      return {
        items: [...state.items, { key: nextId('u'), at: now, live: true, from: 'user', content: action.content }],
        turns: [...state.turns, { id: nextId('t'), at: now, title: action.title, steps: [], done: false }],
        busy: true,
        error: null,
      };
    case 'trace':
      return { ...state, turns: updateLastTurn(state.turns, (t) => ({ ...t, steps: mergeStep(t.steps, action.step) })) };
    case 'bot':
      return { ...state, items: [...state.items, { key: nextId('b'), at: now, live: true, from: 'bot', message: action.message }] };
    case 'transcript':
      return { ...state, items: attachTranscript(state.items, action.text) };
    case 'done':
      return { ...state, busy: false, turns: updateLastTurn(state.turns, (t) => ({ ...t, done: true })) };
    case 'failed':
      return { ...state, busy: false, error: action.error, turns: updateLastTurn(state.turns, (t) => ({ ...t, done: true })) };
    case 'reset':
      return initialState;
    default:
      return state;
  }
}
