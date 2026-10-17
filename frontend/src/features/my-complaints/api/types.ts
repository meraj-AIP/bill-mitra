import type { Discom } from '@/shared/api/types';

/** The neutral states a consumer sees. They never say who is handling the complaint. */
export type MyStatus = 'received' | 'in_progress' | 'waiting_for_you' | 'resolved' | 'closed';
export const MY_STATUSES: MyStatus[] = ['received', 'in_progress', 'waiting_for_you', 'resolved', 'closed'];

export interface MyComplaintRow {
  ticket: string;
  type: string | null;
  type_label: string;
  status: MyStatus;
  /** The status in plain words, in the language asked for. */
  status_label: string;
  created_at: string;
  updated_at: string;
  description: string | null;
  service_masked: string | null;
  bill_month: string | null;
  discom?: Discom | null;
}

export interface MyMessage {
  /** Every staff message arrives as bill_mitra; no names reach the consumer. */
  from: 'you' | 'bill_mitra';
  body: string;
  at: string;
}

export interface MyComplaintDetail extends MyComplaintRow {
  messages: MyMessage[];
}

export interface NewMyComplaint {
  type: string;
  discom: Discom;
  service_number: string | null;
  bill_id: string | null;
  description: string;
}

export interface MyListQuery {
  page: number;
  pageSize: number;
  status: MyStatus | '';
}
