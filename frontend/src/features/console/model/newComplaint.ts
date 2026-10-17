import { MOBILE_PATTERN } from '@/features/auth';
import type { NewStaffComplaint, StaffSource } from '@/features/complaints';
import type { Discom, UnitRef } from '@/shared/api/types';
import { bareUsc, uscShapeOk } from '@/shared/lib/serviceNumber';

export interface StaffDraft {
  source: StaffSource | '';
  type: string;
  discom: Discom | '';
  section: UnitRef | null;
  usc: string;
  mobile: string;
  description: string;
}

export const EMPTY_DRAFT: StaffDraft = { source: '', type: '', discom: '', section: null, usc: '', mobile: '', description: '' };

/** Callers give a mobile with spaces, a +91 or a leading 0; the server wants the bare 10 digits. */
export function bareMobile(value: string): string {
  const digits = value.replace(/[\s-]/g, '');
  return /^(?:\+?91|0)?(\d{10})$/.exec(digits)?.[1] ?? digits;
}

export function draftProblems(d: StaffDraft) {
  return {
    source: !d.source,
    type: !d.type,
    discom: !d.discom,
    usc: d.usc.trim() !== '' && !uscShapeOk(d.usc),
    mobile: d.mobile.trim() !== '' && !MOBILE_PATTERN.test(bareMobile(d.mobile)),
  };
}

export function toBody(d: StaffDraft): NewStaffComplaint | null {
  if (!d.source || !d.type || !d.discom) return null;
  return {
    source: d.source,
    type: d.type,
    discom: d.discom,
    section_id: d.section?.unit_id ?? null,
    service_number: d.usc.trim() ? bareUsc(d.usc) : null,
    contact_mobile: d.mobile.trim() ? bareMobile(d.mobile) : null,
    description: d.description.trim(),
    bill_id: null,
  };
}
