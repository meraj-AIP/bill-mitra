export const ACCOUNT_CSV_COLUMNS = 'name,login,role,unit_code';

/** Header only: a template with sample people in it tends to get imported by mistake. */
export const ACCOUNT_TEMPLATE_HREF = `data:text/csv;charset=utf-8,${encodeURIComponent(`${ACCOUNT_CSV_COLUMNS}\n`)}`;

/**
 * Quotes a cell when it needs it. Text cells that start like a formula get a leading quote so a spreadsheet does not
 * run them; passwords are written as is because a changed password would not work.
 */
export function csvCell(value: string | number, formulaSafe = true): string {
  let text = String(value);
  if (formulaSafe && /^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** Builds the file in memory and hands it to the browser; nothing is kept once the download starts. */
export function downloadCsv(filename: string, lines: string[]): void {
  const url = URL.createObjectURL(new Blob([`${lines.join('\n')}\n`], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
