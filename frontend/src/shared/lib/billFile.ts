/** The bill files the server takes (dashboard upload and the assistant chat), checked first so nobody waits for a 413
 * or 415. The server still checks the content. */
export const BILL_MAX_MB = 12;
const MAX_BYTES = BILL_MAX_MB * 1024 * 1024;
export const BILL_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif', 'application/pdf'];
export const BILL_ACCEPT = `${BILL_TYPES.join(',')},.heic,.heif`;
// Some browsers give iPhone photos no type at all, so the extension is checked too.
const HEIC_NAME = /\.hei[cf]$/i;

export type BillFileIssue = 'type' | 'size';

export function billFileIssue(file: File): BillFileIssue | null {
  if (!BILL_TYPES.includes(file.type) && !HEIC_NAME.test(file.name)) return 'type';
  return file.size > MAX_BYTES ? 'size' : null;
}
