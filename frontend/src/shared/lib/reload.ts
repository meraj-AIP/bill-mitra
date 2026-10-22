/** After a deploy, an open tab still asks for the old page files, which no longer exist. One reload fetches the new
 * ones. The time of the last reload is kept so a file that is really broken shows the error page, not a reload loop. */
const KEY = 'bm-reloaded-at';
const WINDOW_MS = 30_000;

export function isChunkError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '');
  return /dynamically imported module|module script failed|Unable to preload|Loading chunk|Loading CSS chunk/i.test(message);
}

export function reloadedRecently(): boolean {
  try {
    return Date.now() - Number(sessionStorage.getItem(KEY) ?? 0) < WINDOW_MS;
  } catch {
    return false;
  }
}

/** Reloads the page unless it already reloaded in the last 30 seconds. Returns whether it reloaded. */
export function reloadOnce(): boolean {
  if (reloadedRecently()) return false;
  try {
    sessionStorage.setItem(KEY, String(Date.now()));
  } catch {
    // Storage blocked (private mode): reload anyway. A loop is unlikely, because the new files load.
  }
  window.location.reload();
  return true;
}
