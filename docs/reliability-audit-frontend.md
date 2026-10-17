# Frontend reliability audit

Audit of every request path in `frontend/src` against section 6 of [reliability-contract.md](reliability-contract.md),
and what was changed. Done October 2026.

## Findings

| Where | Before | Risk | Now |
|---|---|---|---|
| `app/App.tsx` query defaults | 1 retry on network or 5xx, no backoff, focus refetch off | A short drop shows an error page | 3 retries with jittered backoff (1, 2, 4 s, cap 8 s), network and 5xx only; refetch on focus and reconnect |
| `useBill`, `useMyComplaint`, `useConsoleComplaint` | Own retry: once on anything but 404, so a 403 was retried | Wasted call, slower error | Overrides removed; the shared policy never retries a 4xx |
| `useDemoLogins`, assist and preview queries | `retry: false` | None (assist is a paid model call, preview is a POST) | Kept |
| `shared/api/http.ts` fetch | A dropped connection surfaced as a raw `TypeError: Failed to fetch` | Users saw "Failed to fetch"; no way to tell a lost answer from a request never sent | `NetworkError` with `sent`: false only when the browser was offline before sending or an upload broke off before the whole body left |
| All mutations (about 45) | No retry, no retrying state, raw error text | A blip loses a staff action; nothing says whether it went through | Default retry only when `sent` is false. Idempotent routes opt in with `IDEMPOTENT` (policy PUT, account, role and unit PATCH, password reset, role reset, map unmapped, mark read, read all, AI draft, logout). Never repeated: replies, decisions and decision actions, hand over, send back, status, requests to the consumer, bulk, create and raise complaint, photo, review request, USC start and verify, Send again |
| Lost answer on any mutation | Nothing reloaded | Staff might send the same reply twice | A global `MutationCache.onError` reloads every query on screen when an answer was lost, and the message says to check before trying again |
| Reply, status, decision, hand over, send back, raise complaint, CSV imports | `Alert` with raw message | No retrying state, no Try again | `SendStatus`: offline (queued, sent on reconnect), "Retrying", or the error with Try again for network and 5xx only |
| Dashboard bill upload | fetch, no progress, no retry; preview dropped on failure; a 202 would have been parsed as a report | Lost uploads on a weak phone signal; a queued read would show an empty report | XHR with progress; resent while the photo had not fully arrived; preview kept with Try again and Choose another; 202 job id kept in the URL and polled every 3 s with a "Still reading your bill" card, then the report opens |
| Consumer photo reply | fetch, no progress, no retry | Lost photos | XHR with progress; resent only when the photo never fully arrived, so it is never posted twice |
| CSV imports (accounts, units) | fetch, no retry | Lost import, or created accounts whose passwords were never shown | Resent only when the file never fully arrived; a lost answer says it may have gone through |
| Assistant chat upload `/api/web/upload` | fetch, no retry | Lost photo in the demo chat | Now XHR through `postForm`; no automatic retry yet (follow up: it is content addressed, so it could use the idempotent policy) |
| Assistant chat send `/api/web/messages` (stream) | No retry | None | Kept: a second send is a second message |
| Offline | No indication | People keep tapping Send | Banner under the header; queued mutations wait and go on reconnect |
| Operations | No page | Parked failures invisible | `/admin/operations` (permission `audit.view` or `accounts.manage`): queue counts from `/api/health`, parked jobs with Retry and Dismiss, page, size, kind and sort in the URL |

## Assumed API shapes (to align with the backend)

- `POST /api/bills`: 200 with the report, or 202 with `{ job_id, status, bill_id, detail }`.
- `GET /api/bills/jobs/{job_id}`: the same job object; `status` is `queued`, `running`, `done` or `failed`.
- `GET /api/health`: `queues: { inbox, outbox, extract: { queued, failed }, oldest_queued_s }`.
- `GET /api/admin/operations?page&page_size&kind&sort`: a page of `{ id, kind, ticket, attempts, last_error, created_at, failed_at }`,
  `kind` one of `inbound`, `outbound`, `extract`.
- `POST /api/admin/operations/{kind}/{id}/retry` and `/dismiss`: 204.
