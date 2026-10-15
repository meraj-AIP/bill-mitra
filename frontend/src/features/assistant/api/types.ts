import type { Language } from '@/shared/lib/languages';

export type { Language };

export interface ReplyButton {
  id: string;
  title: string;
}

export type Outbound =
  | { type: 'text'; body: string; language: Language }
  | { type: 'image'; media_id: string; caption?: string | null; language: Language }
  | { type: 'audio'; media_ids: string[]; transcript: string; language: Language; duration_s?: number | null }
  | { type: 'buttons'; body: string; buttons: ReplyButton[]; language: Language }
  | {
      type: 'list';
      body: string;
      button_label: string;
      rows: Array<{ id: string; title: string; description?: string | null }>;
      language: Language;
    };

export type StepMode = 'ai' | 'rules' | 'demo' | 'channel';
export type StepStatus = 'running' | 'done' | 'failed' | 'skipped';

export interface TraceStep {
  id: string;
  label: string;
  status: StepStatus;
  mode: StepMode;
  detail?: string | null;
  ms?: number | null;
}

export type StreamEvent =
  | { kind: 'trace'; trace: TraceStep }
  | { kind: 'message'; message: Outbound }
  | { kind: 'transcript'; text: string }
  | { kind: 'done' };

export interface Uploaded {
  media_id: string;
  mime_type: string;
  size_kb: number;
}

export interface OutgoingMessage {
  kind: 'text' | 'image' | 'document' | 'audio' | 'button_reply';
  text?: string;
  reply_id?: string;
  media_id?: string;
  mime_type?: string;
}

/** What the consumer sent, as saved on the server. */
export interface UserBody {
  kind: OutgoingMessage['kind'];
  text?: string | null;
  reply_id?: string | null;
  media_id?: string | null;
  mime_type?: string | null;
  transcript?: string | null;
}

export type HistoryItem =
  | { id: number; at: string; sender: 'user'; body: UserBody }
  | { id: number; at: string; sender: 'bot'; body: Outbound };

/** One page of saved chat, oldest message first. */
export interface HistoryPage {
  items: HistoryItem[];
  has_more: boolean;
}
