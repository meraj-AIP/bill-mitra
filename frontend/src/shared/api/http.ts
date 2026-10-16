export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
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

async function readError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;
  try {
    const body: unknown = await response.json();
    const detail: unknown = body && typeof body === 'object' && 'detail' in body ? body.detail : null;
    if (typeof detail === 'string') message = detail;
    // FastAPI validation errors (422) send a list of problems; the first one is enough to act on.
    const first: unknown = Array.isArray(detail) ? detail[0] : null;
    if (first && typeof first === 'object' && 'msg' in first && typeof first.msg === 'string') message = first.msg;
  } catch {
    // The body was not JSON; keep the status message.
  }
  return new ApiError(message, response.status);
}

async function request(url: string, init: RequestInit): Promise<Response> {
  const response = await fetch(url, { ...init, credentials: 'same-origin' });
  if (response.ok) return response;
  // Under /api/auth a 401 is an answer (wrong password, not signed in), not an expired session.
  if (response.status === 401 && !url.startsWith('/api/auth/')) unauthorized();
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

export async function postForm<T>(url: string, form: FormData): Promise<T> {
  const response = await request(url, { method: 'POST', body: form });
  return (await response.json()) as T;
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
