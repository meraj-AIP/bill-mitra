# Bill Mitra code review against the BRD

Date: 19 October 2026
Scope: the `main` branch at commit `0490bd3`, checked against the 12 requirements in BRD v0.1.
Paths start at the repository root. `b/` means `backend/app/`.

## Result

Bill Mitra is not ready for production against this BRD.

The code that exists is in good shape. All automated checks pass on SQLite and on Postgres. The demo flows work when the AI providers behave.

There are two problems:

1. Three BRD items are not built: consumption alerts (BR04, marked very important), smart meters (BR09) and the area consumption report (BR12). Most of the other items are partly built.
2. Some inputs crash the app or slow it down. Examples are a bad PDF, a misread date on a photo, or a broken answer from the AI provider. One of these can stop the server for every user.

For the demo, the six problems that can break a demo step are now fixed (see "Update: demo fixes"). The other items under "Must fix before production" matter for real users. They must be fixed before a pilot.

## Update: demo fixes

The goal for now is a safe demo, not production. Features that need data from the DISCOM (BR04 alerts, BR05 meter alerts, BR09 smart meters) stay unbuilt, because no demo step uses them.

We fixed the six problems that can break a demo step with normal use. The table lists each change.

| Problem | What happened before | What we changed | Files |
|---|---|---|---|
| A blurred photo gives an impossible date, such as 30 February or month 13 | The upload failed with an error page instead of a normal answer | The bill model now refuses dates the calendar does not have. The photo reader drops a bad date and keeps the rest of the bill. A bill with no valid start date is priced as one month. | `backend/app/domain/bill.py`, `backend/app/services/vision.py`, `backend/app/flows/meter.py` |
| The AI model returns a reply in the wrong shape, for example a number where a list belongs | The upload returned a server error. On WhatsApp the bill was read four more times. | The reader ignores a part that has the wrong shape. Any other bad reply becomes a normal provider error, which the app already handles. | `backend/app/services/vision.py` |
| The voice service (Sarvam or Soniox) sends an unexpected reply | The whole chat turn failed with "Sorry, something went wrong". A broken audio reply was saved as an empty voice note. | An unexpected reply now counts as "no voice". The explanation goes out as text and the chat continues. A broken audio reply is refused, not saved. | `backend/app/services/tts.py`, `backend/app/services/stt.py`, `backend/app/flows/turn.py` |
| An iPhone photo (HEIC) | The bill was read, but the report page showed a broken image | iPhone photos are now converted to JPEG when they arrive, on the web and on WhatsApp. | `backend/app/core/uploads.py`, `backend/app/channels/whatsapp/router.py` |
| A slow AI provider | One upload waited up to about 4.5 minutes, and the proxy can cut it off before that | Each provider attempt now stops when its time budget runs out. A dashboard upload waits at most 50 seconds (setting `UPLOAD_READ_DEADLINE_S`). After that the read continues in the background, and the page shows "still reading" and checks for the result. | `backend/app/core/retry.py`, `backend/app/flows/report.py`, `backend/app/config.py`, `.env.example`, `ARCHITECTURE.md` |
| A redeploy while a tab is open | The tab showed "Unexpected Application Error" when the user opened Assistant, Console or Review | A page file that is missing after a deploy now reloads the page once. Any other page error shows a clear page with Reload and Start page buttons, and the menu stays in place. The bill status check also stops after an error, instead of asking every 3 seconds forever. | `frontend/src/app/RouteError.tsx`, `frontend/src/app/App.tsx`, `frontend/src/app/main.tsx`, `frontend/src/shared/lib/reload.ts`, `frontend/src/features/dashboard/api/billsApi.ts` |

New tests in `backend/tests/test_demo_safety.py` cover each fix. The results after the change:

| Check | Result |
|---|---|
| Backend tests on SQLite | 529 passed, 20 skipped |
| Backend tests on Postgres 16 | 547 passed, 2 skipped |
| `ruff check .` | Pass |
| `npm run typecheck`, `npm run lint`, `npm run build` | Pass |

These steps are still needed before the demo. They are not code changes:

1. Choose the two or three demo bills now. Do not use a bill with a very unusual past month, a 45 day period or large arrears. The forecast and the "why is my bill high" answer can look wrong on those bills (see BR06 and BR11 below).
2. Run all eight demo steps on the demo server, with the live keys, the phone the presenter will use, and the staff accounts for the demo.
3. Make sure that each staff account covers the section printed on the demo bill. If it does not, the case does not reach the section AE in step 6.
4. Run the backend on the server or in Docker. It does not start on Windows.
5. Do not deploy on the day of the demo. Deploy the day before, and open each page once after the deploy.

The items under "Must fix before production" that are not in the table above are still open. They matter for real users, not for a controlled demo.

## How we checked

We ran these checks:

| Check | Result |
|---|---|
| Backend tests on SQLite (Linux container) | 494 passed, 20 skipped |
| Backend tests on Postgres 16 | 512 passed, 2 skipped |
| `ruff check .` | Pass |
| `npm run typecheck` | Pass |
| `npm run lint` (zero warnings) | Pass |
| `npm run build` | Pass |
| Frontend files under 300 lines | Pass (largest is 208) |

We also read the code for each BRD item and ran small test scripts against the engine and the API. The scripts are not in the repository.

We did not do these things:

- Test with live OpenAI, Sarvam, Soniox or WhatsApp keys.
- Click through the eight demo steps in a browser.
- Read the nginx configuration, because it is not in the repository.

## BRD coverage

| BRD item | Status | In one line |
|---|---|---|
| BR01 Solar bills | Partial | Reads import, export and net units. No export credit or banking. |
| BR02 Role based access | Partial | Good permission model. Three leaks found (see below). |
| BR03 Ticket approvals | Partial | One extra approver for bill reviews only. Complaints have no approval step. |
| BR04 Consumption alerts | Missing | Nothing compares usage with the consumer's average. Nothing is sent. |
| BR05 Meter issue alerts | Partial | Status code 02 is shown as "stuck", but nobody is alerted. |
| BR06 Reasonable predictions | Partial | Shown as a range. One unusual month can inflate it badly. |
| BR07 AI response validation | Partial | Every AI text passes the number guard, but the guard has holes. |
| BR08 Human approval | Partial | Money decisions go to people. There is no "ambiguous" queue. |
| BR09 Smart meters | Missing | No smart meter connection of any kind. |
| BR10 Billing days and slabs | Partial | Slab limits scale with billing days. Three charges do not. |
| BR11 High bill questions | Partial | Gives fixed reasons. Never asks about appliances. Sometimes states guesses as facts. |
| BR12 Area consumption report | Missing | The console counts bills per section. It does not show units consumed per area. |

## Must fix before production

These items can crash the app, lose data, show the wrong amount, or show one person's data to another person.

1. **Large PDF can stop the server.** `b/services/vision.py:149-160` renders each PDF page at 2 to 8 times its size, with no limit on pixels. A 331 byte PDF became a 100 megapixel image in our test. A larger page needs more than 3 GB of memory. The render also blocks every other request while it runs. Any registered consumer or WhatsApp sender can trigger this. Fix: cap the render at about 25 megapixels, and run it in a worker thread.

2. **A misread date on a bill breaks the upload.** The date patterns in `b/domain/bill.py:44-47` and `b/services/vision.py:194` accept impossible dates such as `2025-02-30` and month `13`. Later, `bill.py:90` and `month_date()` fail on them. `b/flows/report.py:132`, `b/flows/bill.py:180` and `b/flows/intake.py:95` do not catch this, so the consumer gets an error page. Fix: parse the dates during validation, and drop any value that does not parse. Fixed for the demo (see "Update: demo fixes").

3. **A broken AI answer gives a server error.** If the vision model returns `line_items` as a number instead of a list, `_clean` in `b/services/vision.py:204-210` fails and `POST /api/bills` returns 500. On WhatsApp the same bill is read again four times, and each read costs money. TTS and STT fail the same way on unexpected JSON (`b/services/tts.py:66`, `b/services/stt.py:56-69`). An invalid audio answer is saved as an empty voice note. Fix: check the types, catch `TypeError`, and decode with `validate=True`. Fixed for the demo.

4. **Any signed-in user can open any bill photo.** `GET /api/media/{id}` in `b/api/catalog.py:53` checks only that the user is signed in. It does not check who owns the photo. The ids are hard to guess, but bill photos carry names and service numbers. Fix: allow the owner, plus staff whose units cover the bill.

5. **Two approvers can approve the same decision.** On Postgres, `approve()` in `b/store/review.py:186-196` reads first and then updates by id only. When two approvers click at the same moment, both succeed. The consumer is told twice, and the audit log gets two entries. An approve can also undo a reject that happened at the same moment. `create_decision()` (lines 167-183) has the same gap, so one case can get two decisions. Fix: add `AND status = 'pending_approval'` to the update and check the row count, as `reject()` already does. Use `tx(immediate=True)` in `create_decision()`.

6. **Officers see other areas' numbers.** The console summary filters by DISCOM only, not by the officer's units (`b/api/console.py:19`). An officer of one section sees the counts and average units of every section in the DISCOM. Fix: apply the same unit scope that complaints use.

7. **The auditor can change data.** The auditor role is read only, but `b/api/operations.py:16` lets it retry and dismiss parked items. Fix: require `accounts.manage` for the write routes.

8. **An AE can avoid the approval limit.** `custom()` in `b/domain/review.py:107-109` ignores `ae_limit`. With the limit at Rs 100, a custom reduction of Rs 5000 was approved at once in our test. Fix: apply the limit to custom decisions too.

9. **Uploads have no size limit before sign in.** FastAPI reads the whole form before it checks the session. Anyone can send gigabytes to `/api/bills` and `/api/web/upload`. Fix: set `client_max_body_size 13m` in nginx, and reject a large `Content-Length` in middleware.

10. **The login rate limit can be bypassed.** `Dockerfile:38` trusts `X-Forwarded-For` from any source, so a client can send a new address with each request. Fix: trust only the nginx address, or make nginx set the header to `$remote_addr`.

11. **The "no consumer data in logs" rule is broken.** `log.exception` in `b/channels/whatsapp/router.py:84` and `b/core/service.py:129` writes full error traces. These traces can include the text of the message. Fix: log the type of the error only, as the scheduler already does.

12. **Production settings are too loose.** The session cookie is not `Secure` by default. The production check in `b/config.py:102-107` also accepts the sample admin password from `.env.example`. Fix: refuse to start in production without `COOKIE_SECURE`, or with the sample password.

## Fix before the demo

These items do not break data, but they can make the demo fail or look wrong.

1. **A redeploy breaks open tabs.** The frontend has no error page and does not reload missing files (`frontend/src/app/App.tsx:76-120`). After a redeploy, an open tab that opens Assistant, Console or Review shows "Unexpected Application Error". Fix: add a root `errorElement` that reloads once on a chunk error. Do not deploy just before the demo. Fixed.

2. **A slow AI provider makes uploads wait too long.** The retry budget in `b/core/retry.py:89` does not limit one attempt. One read took 91 seconds against a 60 second budget. One bill can take about 4.5 minutes. The upload is synchronous, so nginx can time out first. Fix: limit each attempt to the time left in the budget. Fixed, and a dashboard upload now waits 50 seconds at most.

3. **One slow queue stops the others.** The extract, outbox and inbox jobs run in one loop (`b/flows/recovery.py:56`). During an outage, 20 stuck bill reads can delay replies for about 30 minutes. Fix: give each queue its own task.

4. **A WhatsApp message can be lost.** The webhook marks a message as seen before it queues it, in a separate transaction (`b/channels/whatsapp/router.py:157-158`). If queueing fails, the retry from Meta is ignored. Fix: do both in one transaction.

5. **The page checks forever after an error.** If a bill read job returns 404, the dashboard asks again every 3 seconds without end (`frontend/src/features/dashboard/api/billsApi.ts:67`). Fix: stop on an error. Fixed.

6. **iPhone photos do not show.** HEIC uploads are saved as `.bin`, so the report page shows a broken image (`b/store/media.py:14`). Fix: save the converted JPEG. Fixed.

7. **The public tariff calculator fails on a bad month.** `GET /api/tariffs/calculate?month=2026-13` returns 500 and needs no sign in (`b/api/catalog.py:84`). Fix: check the month range.

8. **Chat messages have no rate limit.** `/api/web/messages` (`b/channels/web.py:46`) can start paid vision, AI and voice calls with each message. Fix: add a limit per account.

## BRD gaps in detail

### BR04 Consumption alerts (very important, not built)

Nothing in the code tracks usage during a billing period or compares it with the average. Staff alerts exist, but `b/api/alerts.py` blocks consumers. The closest feature is the meter photo check in `b/flows/meter.py:32`. It warns only when the estimate crosses 200 units, and only when the consumer sends a photo.

To build BR04, the team needs:

1. Daily or frequent readings for each service number. These come from smart meters (BR09) or from meter photos.
2. An average for each consumer, from the billing history.
3. A record of each alert sent, so that each level (50%, 75%, 100%) goes out once per billing period.
4. A scheduled job that checks the levels.
5. An approved WhatsApp template, because alerts arrive outside the 24 hour window.
6. Consumer opt in.

### BR05 Meter issue alerts

`b/domain/meter_status.py:14` maps status 02 to "stuck". The consumer sees a note in the explanation. The DISCOM sees the status only when a complaint is already open, and no alert is ever sent. The code has no rule for a reading that did not change, for zero use, or for several estimated months in a row. If a meter photo shows a reading below the last bill, `b/flows/meter.py:22` sets the units to 0 and does not flag it.

### BR06 Predictions

The forecast is shown as a range of plus or minus 8 percent, and the engine prices it. Our tests found these problems:

- A 45 day bill of 300 units predicts 270 units for the next month. It must be about 180. Past bills are not adjusted for their billing days either.
- History of 150, 150 and 3000 units predicts 1031 units and Rs 9031. Nothing removes an unusual month.
- Old history from 2023 is used for a 2025 forecast and labelled "your last 3 months".
- A history month of `2025-13` from a photo stops the forecast with an error. Fixed: the reader now drops that month.

### BR07 AI guard

Every AI text goes through the number guard in `b/domain/conversation/guard.py`, and the guard falls back to the template when a check fails. But the guard has these holes:

- It does not see numbers written as words, such as "two thousand rupees" in English, Telugu or Hindi.
- It always allows 0 to 10, 12, 24, 30, 50, 100, 101, 200, 201, 300, 400, 800 and the years 2022 to 2027. So "You used 300 units, Rs 800" passes for any bill.
- It ignores multipliers. "Rs 2k" and "Rs 2 lakh" both pass.
- It does not check what a number means. Swapping the units and the amount passes.
- It does not check month names in dates.
- Cached explanations are not checked again (`b/flows/bill.py:156-160`).

When the guard fails, the template answer goes out and no person reviews the case. The BRD asks for review or an agreed fallback, so the team needs a decision here.

### BR10 Billing days and slabs

The slab limits scale correctly with billing days. For 150 units starting in September, the first slab ends at 133 units for 20 days, 93 for 28 days and 75 for 45 days.

Three charges do not scale with billing days:

- The fixed charge stays at Rs 10 for any number of days (`b/domain/tariff/engine.py:114`).
- The customer charge band uses the 30 day limits (`engine.py:83-87`).
- The Gruha Jyothi limit stays at 200 units. Over 45 days, 201 units (about 134 a month) loses the full subsidy: Rs 876.86 instead of Rs 0 (`engine.py:121`).

The DISCOM must confirm the correct rule for each of these. Also:

- When the start date is missing, the bill is priced as 30 days, even if it shows 45 billing days.
- Periods under 15 days are billed as 15 days.
- `b/tests/test_tariff.py` has no test for 20, 28 or 45 days, although the BRD names those examples.

### BR11 High bill questions

"Why is my bill high" works in English, Telugu and Hindi, but it returns a fixed template (`b/domain/conversation/composer.py:92-102`). It never asks about appliances, guests or changes in use. Our tests found these problems:

- It says "Nothing unusual this month" when the bill has Rs 3000 in arrears or a Rs 900 true up. It also says this when the bill was not fully checked. Arrears, true up, surcharge and FSA are never named as causes.
- A commercial bill of 250 units gets the household text "You crossed 200 units", followed by "adds Rs 0".
- "My bill increased because I bought an AC" ignores the cause the consumer gave.

### BR12 Area consumption report (not built)

The console has a table of sections (`b/store/console.py:121-124`). It counts bills read and average units for uploaded bills only, over the last 7 to 365 days. It does not show total units. It does not roll up to division, circle or district, and it has no date range or bill month filter. If the same bill is uploaded twice, it counts twice.

### BR01, BR03 and BR08 in short

- **Solar:** extra export is lost. With import 100 and export 250, net is 0 and the 150 unit credit is not carried forward. A negative `export_units` from a misread adds units instead of failing. A negative `billed_units` stops pricing with an error. There is no test for a household solar bill.
- **Approvals:** there are two levels at most, for bill reviews only. Out of the box (`b/domain/review.py:29`), no decision needs a second approval. The same approver can approve and also mark it applied.
- **Human review:** a low confidence photo goes back to the consumer, not to staff. A guard failure is not reviewed. Revisions are marked applied automatically when the DISCOM records match (`b/flows/automation.py:141`).

## Small items

- The backend does not start on Windows, because `b/store/db.py:4` imports `fcntl`. Production runs in Linux, so this affects developers only. Note it in the README, or use a lock that works on both.
- The Starlette test client warns that `httpx` support is going away.
- `test_access_matrix.py` does not cover proposals, operations, alerts, media, or most write routes. The leaks in items 4, 6 and 7 above passed the suite for this reason.

## What works well

- The rule engine gives every amount. No language model makes up a rupee figure.
- Every AI text path goes through the guard and falls back to the template.
- Uploads are typed by their content, not by their file name. We fed 1,600 broken image and PDF files, and none of them crashed the app outside the existing error handling.
- WhatsApp signatures are checked with a safe compare. Messages are refused when no app secret is set.
- Queued work recovers after a restart. Outbox, inbox and extract jobs all have sweeps.
- Each scheduled job fails on its own without stopping the others.
- Nobody can approve or apply their own decision. Every action is audited.
- The frontend menus match the backend permissions.
- Every provider key is optional. The app starts and says what is off.

## Decisions the DISCOM must make

These answers change what the team builds:

1. Which smart meter system to connect to, and how often it gives readings (BR04, BR09).
2. The average period for alerts, the channel, and whether DISCOM also gets consumption alerts (BR04).
3. What "2" means in "2 means the meter is stuck" (BR05).
4. Whether the fixed charge, customer charge band and Gruha Jyothi limit scale with billing days (BR10).
5. What happens when the AI guard fails: template, retry, or staff review (BR07).
6. Which approvals each ticket type needs, and in what order (BR03).
7. What "area" means in the report: section, division or district (BR12).
8. How solar export credit is carried forward (BR01).

## Suggested order of work

1. Fix items 1 to 8 under "Must fix before production". Each one is small.
2. Fix the items under "Fix before the demo", and do not deploy on the day of the demo.
3. Add tests for 20, 28 and 45 day bills, and for the routes that the access test does not cover.
4. Close the guard holes and fix the high bill answer (BR07, BR11).
5. Build BR12, because it uses data the app already holds.
6. Build BR04 and BR05 alerts when the DISCOM answers questions 1 to 3.
