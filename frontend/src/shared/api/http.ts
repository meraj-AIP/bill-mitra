export type ErrorExtras = Record<string, unknown>;

/**
 * A refused or failed request. message is the server's own sentence; code, ref and extras come from the error
 * envelope {detail: {code, message, ref, ...extras}}. Old string details and validation lists still work.
 * serverText is false when the server said nothing usable, so callers fall back to their own words.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null = null,
    readonly ref: string | null = null,
    readonly extras: ErrorExtras = {},
    readonly serverText = true,
  ) {
    super(message);
  }
}

/**
 * The server could not be reached. sent is false only when we know the whole request never left the browser
 * (offline before sending, or an upload that broke off part way), so a retry cannot repeat an action.
 */
export class NetworkError extends Error {
  constructor(readonly sent: boolean) {
    super(sent ? 'The connection dropped before the server answered.' : 'Could not reach the server. Check your connection.');
  }
}

let unauthorized: () => void = () => undefined;

/** The app registers one handler that sends a signed-out user to the login page. */
export function onUnauthorized(handler: () => void): void {
  unauthorized = handler;
}

export function isStatus(error: unknown, status: number): boolean {
  return error instanceof ApiError && error.status === status;
}

// Kept as the message when the server said nothing usable, so a screen that still prints error.message reads sensibly.
const NO_TEXT = 'Something went wrong. Please try again.';
const text = (value: unknown): string | null => (typeof value === 'string' && value.trim() ? value.trim() : null);

function fromDetail(detail: unknown, status: number, headerRef: string | null): ApiError | null {
  const plain = text(detail);
  if (plain) return new ApiError(plain, status, null, headerRef);
  // Old FastAPI validation errors (422) send a list of problems; the first one is enough to act on.
  const first: unknown = Array.isArray(detail) ? detail[0] : null;
  const msg = first && typeof first === 'object' && 'msg' in first ? text(first.msg) : null;
  if (msg) return new ApiError(msg, status, null, headerRef);
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null;
  const { code, message, ref, ...extras } = detail as Record<string, unknown>;
  const said = text(message);
  return new ApiError(said ?? NO_TEXT, status, text(code), text(ref) ?? headerRef, extras, said !== null);
}

async function readError(response: Response): Promise<ApiError> {
  // The ref is also sent as a header, so a body that is not JSON (a proxy error page) can still be traced.
  const headerRef = text(response.headers.get('X-Request-Id'));
  try {
    const body: unknown = await response.json();
    const found = fromDetail(body && typeof body === 'object' && 'detail' in body ? body.detail : null, response.status, headerRef);
    if (found) return found;
  } catch {
    // The body was not JSON; the status alone says what kind of failure it was.
  }
  return new ApiError(NO_TEXT, response.status, null, headerRef, {}, false);
}

function checkStatus(url: string, status: number): void {
  // Under /api/auth a 401 is an answer (wrong password, not signed in), not an expired session.
  if (status === 401 && !url.startsWith('/api/auth/')) unauthorized();
}

async function request(url: string, init: RequestInit): Promise<Response> {
  if (!navigator.onLine) throw new NetworkError(false);
  let response: Response;
  try {
    response = await fetch(url, { ...init, credentials: 'same-origin' });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new NetworkError(true);
  }
  if (response.ok) return response;
  checkStatus(url, response.status);
  throw await readError(response);
}

function jsonInit(method: string, body: unknown): RequestInit {
  if (body === undefined) return { method };
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}

export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await request(url, { signal: signal ?? null });
  return (await response.json()) as T;
}

/** POST, PUT, PATCH or DELETE with an optional JSON body. A 204 resolves to undefined, so call it with T = void. */
export async function sendJson<T>(url: string, body?: unknown, method: 'POST' | 'PUT' | 'PATCH' | 'DELETE' = 'POST'): Promise<T> {
  const response = await request(url, jsonInit(method, body));
  return (response.status === 204 ? undefined : await response.json()) as T;
}

/** POST and hand back the raw response, for streamed replies. */
export async function postJson(url: string, body?: unknown): Promise<Response> {
  return request(url, jsonInit('POST', body));
}

export interface Sent<T> {
  status: number;
  data: T;
}

/**
 * POST a form with XMLHttpRequest, because fetch cannot report upload progress. It also tells a body that never
 * fully arrived (safe to send again) from a lost answer (the server may have acted on it).
 */
export function uploadForm<T>(url: string, form: FormData, onProgress?: (fraction: number) => void): Promise<Sent<T>> {
  if (!navigator.onLine) return Promise.reject(new NetworkError(false));
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let uploaded = false;
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress?.(e.loaded / e.total); };
    xhr.upload.onload = () => { uploaded = true; onProgress?.(1); };
    xhr.onerror = () => reject(new NetworkError(uploaded));
    xhr.ontimeout = xhr.onerror;
    xhr.onload = () => {
      const empty = [204, 205, 304].includes(xhr.status);
      const response = new Response(empty ? null : xhr.responseText,
        { status: xhr.status, headers: { 'X-Request-Id': xhr.getResponseHeader('X-Request-Id') ?? '' } });
      if (response.ok) {
        if (empty) return resolve({ status: xhr.status, data: undefined as T });
        void response.json().then((data: T) => resolve({ status: xhr.status, data }), reject);
        return;
      }
      checkStatus(url, xhr.status);
      void readError(response).then(reject);
    };
    xhr.open('POST', url);
    xhr.withCredentials = true;
    xhr.send(form);
  });
}

export async function postForm<T>(url: string, form: FormData, onProgress?: (fraction: number) => void): Promise<T> {
  return (await uploadForm<T>(url, form, onProgress)).data;
}

/** Read a newline-delimited JSON stream, calling onLine for each parsed object as it arrives. */
export async function readNdjson(response: Response, onLine: (value: unknown) => void): Promise<void> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf('\n');
    while (newline >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (line) onLine(JSON.parse(line));
      newline = buffer.indexOf('\n');
    }
  }
}
