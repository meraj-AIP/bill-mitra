# Web chat parity

WhatsApp is not connected on the demo servers, so the web chat (the Assistant page) stands in for it. One device is
the consumer in the web chat, another is staff in the console. Anything WhatsApp would carry to the consumer has to
land in their web chat, and anything they send there has to reach the complaint or case it answers.

## One path in

A message outside the consumer's own turn reaches the web chat through `notify.to_web_chat` in
`backend/app/services/notify.py`. Complaint messages go `notify.reply / status / send` to `_deliver`, which picks
WhatsApp or the web chat from the complaint's channel. The message is stored in `chat_messages` as the same message
model the chat renders. A text WhatsApp would send as an approved template outside the 24 hour window is stored as
the text itself. A deferred bill read runs the consumer's turn again, so its report is stored by the turn's own
recording (`service._recording`), the same way the live chat stores replies.

## Audit

| What goes out | Where it starts | Web chat before | Web chat now | How the consumer's answer gets back |
|---|---|---|---|---|
| Staff reply, bulk explanation, Send again | `api/complaints.py`, `api/complaint_actions.py` via `notify.reply` | Yes (`_to_web_chat`, commit d305674) | Yes | A reply that asks something sets `info:<ticket>`; the next text or photo in the chat is filed by `complaint.capture_info` |
| Status line: resolved, rejected, reopened | `_change_status` via `notify.status` | Yes | Yes | Not an ask |
| Request for information (complaint or case) | `complaint.ask` via `notify.send`, also from approved proposals | Yes | Yes | `capture_info`: text or photo lands on the thread and answers the open request |
| Bill photo request on a reading complaint with no bill | `intake._ask_for_bill` | Yes | Yes | Same, through `info:<ticket>` |
| Request for earlier bills | `case_bills.request_months` (no turn: web report or staff raise) | Yes | Yes | A bill photo in the chat is read and filed by month and service number (`attach_upload`); "I don't have them" closes the request (`no_bills_from_chat`) |
| Decision: revised, correct, withdrawn, applied (by hand or automatic) | `cases.tell_decision`, `cases.tell_consumer` | Yes | Yes | Not an ask |
| Reminder and lapse of a request | `automation.run_reminders`, `run_lapses` via `tell_consumer` | Yes | Yes | As for the request itself |
| Complaint logged by the call centre for a caller's mobile | `api/complaint_raise.py` | No: owned by the WhatsApp key, every update failed as not connected | Fixed: with WhatsApp off, owned by the consumer account on that mobile, channel web | As any web complaint |
| Bill read deferred while the reader is down | `bill._defer`, `extract.run_due` | No: the web chat gave up at once | Fixed: queued like WhatsApp; the report, the last try's Try again, or the gave up line land in the chat | The report's buttons work as in any turn |
| Hand over, send back, case assigned, decision returned | `flows/handoff.py` | Nothing to the consumer | Same, by design | Staff only; no names reach the consumer |
| Delivery retries, template fallback, `delivery_failed` | `services/delivery.py`, `notify.delivery_failed` | WhatsApp only | Same | Nothing to retry: a web chat write is immediate |
| Service number code, sign in code | `usc.start`, `mobile_auth` via `notify.send_code` | No | Same, by design | The code proves the person holds the registered mobile; showing it to whoever is signed in would defeat it |
| Alerts | `store/alerts.raise_alert` | Staff only | Same | Not consumer facing |

## Without a reload

- Consumer: the Assistant page polls `GET /api/web/history?after=<id>` every 5 seconds while the tab is visible and
  no turn is streaming. Each streamed message carries its stored `chat_id`, and a `state` event carries the id of what
  the person sent, so the poll skips what the page already shows.
- Staff: the complaint page, the inbox, the review case page, the case queue and the alerts bell refetch every 10
  seconds (`LIVE_MS`). TanStack pauses them while the tab is hidden.

A staff ask made while the consumer's own turn is running used to be lost when the turn saved the state it had
loaded. `repos.save_user` now writes `awaiting` only if nobody changed it during the turn.

## Known limits

- A bill sent from the My bills page still files under a case, but says so on that page, not in the chat, as before.
