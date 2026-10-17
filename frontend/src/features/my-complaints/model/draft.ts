import { descriptionOk, type ComplaintType } from '@/features/complaints';
import type { Discom } from '@/shared/api/types';
import { bareUsc, uscShapeOk } from '@/shared/lib/serviceNumber';

import type { NewMyComplaint } from '../api/types';

export interface Draft {
  type: ComplaintType | null;
  discom: Discom | null;
  usc: string;
  billId: string;
  description: string;
}

/** The request body, or null while something required is missing or wrong. */
export function toRequest(d: Draft): NewMyComplaint | null {
  const usc = d.usc.trim();
  if (!d.type || !d.discom || (usc && !uscShapeOk(usc)) || !descriptionOk(d.description)) return null;
  return { type: d.type.code, discom: d.discom, service_number: usc ? bareUsc(usc) : null, bill_id: d.billId || null, description: d.description.trim() };
}
