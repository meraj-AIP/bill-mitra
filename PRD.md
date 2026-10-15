# Bill Mitra: Product Requirements Document

Personalized Billing Assistance on WhatsApp for Telangana electricity consumers.

| Item | Detail |
|---|---|
| Product | Bill Mitra |
| Team | AI Planet, Hyderabad |
| Challenge | EnergyTech Innovation Challenge, Department of Energy, Government of Telangana |
| Problem statement | Personalized Billing Assistance (Agentic AI) |
| Partners running the challenge | AIKAM Global, IIIT Hyderabad, GDG Hyderabad |
| Status | Shortlisted, top 30. Immersion Day jury session, 16 Oct 2026, IIIT Hyderabad |
| Version | Draft 1, 15 Oct 2026 |

## 1. Summary

Bill Mitra is a WhatsApp assistant for household electricity consumers in Telangana.

A consumer sends a photo of the bill. A PDF, the bill SMS or just the number of units also work. Bill Mitra reads it, checks every charge against the TGERC tariff, and explains the bill in Telugu as a voice note with text. It says whether the bill matches the tariff. It estimates next month. It warns before the home crosses 100 or 200 units. It suggests how to save in plain terms, such as minutes of AC per day. If a charge is wrong, the consumer can raise a complaint once they agree. The complaint is recorded in Bill Mitra and answered by a department officer. It is not connected to 1912 yet, so the consumer is also told to call 1912.

English, Hindi and Urdu are also supported. Urdu is text only for now.

One rule runs through the product: **rules calculate, AI explains.** A deterministic engine does every calculation from versioned tariff tables. The language model only writes sentences. A number guard checks every figure the model writes. If any figure does not trace back to the engine, the reply falls back to a checked template.

This build is a web app with sign in and three roles. Consumers get a bill dashboard and a WhatsApp preview chat with a "Behind the reply" trace panel. Officers get a Department console and a complaints inbox. Admins manage accounts and read the audit log. A How it works page holds the tariff explorer. The WhatsApp Cloud API adapter is built and switches on with environment settings. There is no mock data anywhere. Without an OpenAI key, bill reading is off and the consumer types the units.

## 2. Problem

Most households cannot check their own electricity bill. The reasons are simple.

- **Slabs change with usage.** The rate depends on which group the home falls in that month. A home at 100 units pays LT-I(A) rates. At 101 units it moves to LT-I(B) and every unit is billed at the higher rates.
- **The 200-unit cliff.** Gruha Jyothi gives free supply up to 200 units. At 201 units the household loses the whole benefit for that month, not just the extra unit. It also moves to LT-I(C), where the first 200 units cost Rs 5.10 each. One extra unit can cost hundreds of rupees.
- **FSA.** The fuel cost adjustment changes month to month. Few people know what it is.
- **True-up.** From November 2026 a true-up line recovers approved power costs from 2022 to 2024. It looks like a new, unexplained charge.
- **Arrears.** Unpaid amounts from past months are added to the total. Many people read the total as this month's bill and think it doubled.
- **The paper bill is in English.** Most consumers speak Telugu. Many have low literacy. The bill uses codes like LT-I(B) and terms like "customer charges" that nobody explains.

The result: consumers call 1912 or visit the counter to ask "why is my bill so high". Staff answer the same questions every day. Real billing errors are hard to spot. People lose Gruha Jyothi without knowing they were close to the limit.

## 3. Goals and success measures

### Goals

1. A consumer understands their bill in their own language within a minute of sending it.
2. Every figure Bill Mitra says is correct against the tariff, and can be traced.
3. Households are warned before they cross 100 or 200 units, not after.
4. Real overcharges reach a department officer with the evidence attached, and the reply reaches the consumer.
5. The Department sees what people ask and where bills go wrong, by section.

### Pilot measures (all targets proposed, to agree with the DISCOM)

| Measure | How we count it | Proposed target |
|---|---|---|
| Bills trusted first time | Share of bills whose rule checks pass on the first read, without a re-read or a retake | 80 percent or more |
| Audit accuracy | Bill Mitra's line verdicts compared with a manual check by DISCOM staff on a set of real bills | 98 percent or more agreement |
| Figures traced | Share of replies where every number traces to the engine (guard pass or template) | 100 percent |
| Time to answer | From photo received to first reply, live providers | Under 20 seconds for 9 in 10 bills |
| Complaint quality | Share of Bill Mitra complaints that officers mark Resolved as real billing errors (not Rejected) | To be set after month one |
| Complaint resolution | Days from ticket to Resolved or Rejected; none open over 7 days | Faster than the current 1912 baseline |
| Repeat use | Households that send a second bill or ask a follow-up question | 40 percent or more |
| Language reach | Share of conversations in Telugu | Tracked, no target |

## 4. Users

| User | Need | How Bill Mitra serves them |
|---|---|---|
| Household consumer (primary) | Understand the bill, know if it is right, avoid a big jump next month. Often a Telugu speaker with low literacy, already on WhatsApp. | Voice note in Telugu with short text, buttons instead of typing, answers to common questions, slab warnings, one-tap complaint. |
| Department officers | Answer complaints quickly and the same way every time. See volume, outcomes and hot spots. | Complaints inbox with the audit lines and bill photo, a thread, reply and status change. Console with reading quality, complaints by status, overdue tickets and CSV export. Tariff explorer to check any unit count. |
| Admin | Control who can see consumer data. | Staff accounts (create, edit, deactivate, reset password) and an audit log of admin and complaint actions. |

## 5. Scope

### In this build

- Sign in, consumer registration (mobile and password, with consent to the privacy notice) and three roles: admin, officer (optionally limited to one DISCOM), consumer.
- Consumer dashboard: upload a bill and get the full report, history, next month and a plain explanation in four languages.
- WhatsApp preview chat. The phone UI shows only message types WhatsApp supports: text, image, voice note, reply buttons and lists.
- Full conversation engine: two pass bill reading with rule checks, tariff engine, line audit, explanation, number guard, prediction, warnings, savings, what-if, complaint preview and filing.
- "Behind the reply" trace panel showing each step, tagged as rules, AI or channel.
- Department console with real metrics only, complaints inbox with replies, CSV export.
- Admin pages for accounts and the audit log.
- Privacy notice, STOP and account deletion, retention job.
- How it works page with the tariff explorer and WhatsApp readiness status.
- WhatsApp Cloud API adapter, built and tested, switches on with env settings.

### Pilot and later (not built)

These are **not in this build**. They need DISCOM or Department access, or come after the pilot.

- Live WhatsApp Business number and approved message templates.
- DISCOM billing API. Today history comes only from the usage table printed on the bill and the account's own earlier uploads.
- 1912 grievance API. Today tickets are recorded in Bill Mitra only.
- SMS OTP for consumer sign up (needs an SMS gateway).
- Urdu voice notes.
- Proactive mid-month reminders (needs WhatsApp templates and opt-in).
- Audit of non-domestic (LT-II and other) bills.
- Live FSA values per month from the DISCOM.
- Assigning a complaint to a named officer, and SLA escalation.

## 6. Functional requirements

Paths are relative to the repository root. `backend/app` is shortened to `b/` and `frontend/src/features` to `f/`.

| ID | Requirement | Where it lives | Status |
|---|---|---|---|
| FR-1 | Accept a bill photo (JPG, PNG, WebP, HEIC) and read units, readings, billing days, load, category, line items, arrears, total, bill and due dates. The upload type is checked from the file bytes, not the name. A first low-detail look sorts the image into electricity bill, meter, other bill or other, and stops non-bills. A careful high-detail read follows. Tall thermal spot-billing slips are read as overlapping crops, because the API shrinks images to about 768 px on the short side. | `b/flows/bill.py`, `b/services/vision.py`, `b/domain/bill.py`, `b/core/uploads.py` | Built |
| FR-2 | Accept a PDF bill of up to 3 pages and read the page that is a bill. | `b/services/vision.py` | Built |
| FR-3 | Accept the DISCOM bill SMS pasted as text. Read service number, units, amount, due date and month. | `b/services/sms_parser.py`, `b/flows/question.py` | Built |
| FR-4 | Accept typed units ("214" or "214 units") when there is no bill or the photo failed. Calculate the bill from units. | `b/domain/conversation/intents.py` (`parse_units`), `b/flows/question.py` | Built |
| FR-5 | Accept a mid-month meter photo. Use the last bill's reading and date to project month-end units and amount, and warn if 200 will be crossed. | `b/flows/meter.py` | Built |
| FR-6 | Rule checks decide trust: present minus previous reading equals units, charges add up to the bill amount, bill amount plus arrears equals total due, billing days match the dates. If a check fails, the bill is read once more, naming only the failed check (never the expected numbers). If it still fails, the consumer is asked to retake the photo with the reason. Nothing is guessed. | `b/domain/capture.py`, `b/services/vision.py`, `b/flows/bill.py` | Built |
| FR-7 | If the image is not an electricity bill, say so and ask for a TGSPDCL or TGNPDCL bill. | `b/flows/bill.py`, `not_a_bill` text | Built |
| FR-8 | Non-domestic bill (for example LT-II shop): read and explain, but mark it "not checkable" and point to 1912. | `b/domain/audit.py`, `non_domestic` text | Built |
| FR-9 | Tariff engine: compute energy (by slab group, pro-rated by billing days), fixed, customer charge, duty and FSA from versioned tables. Pick the tariff version in force for the bill month. | `b/domain/tariff/engine.py`, `b/domain/tariff/tables.py` | Built |
| FR-10 | Tariff tables for FY2023-24 to FY2026-27, with effective dates, true-up rule and a list of items still to verify. | `b/domain/tariff/tables.py` | Built (values to confirm) |
| FR-11 | Line audit: compare each printed charge with the engine. Each line is match, over, under, missing or not checkable. Overall status is verified, mismatch, partial, not checkable or calculated. | `b/domain/audit.py` | Built |
| FR-12 | Rounding tolerance of Rs 1 per line before a line is called over or under. | `b/domain/audit.py` (`TOLERANCE`) | Built |
| FR-13 | Explain true-up, arrears, net metering and the late payment surcharge when present. True-up is explained, not audited. | `b/domain/audit.py`, `b/domain/conversation/composer.py` | Built |
| FR-14 | Explanation in Telugu, English, Hindi and Urdu, written in the order a person would say it: what you pay (the printed bill amount), slab group, Gruha Jyothi, audit result, change from last month, true-up, saving tip, next month. | `b/domain/conversation/composer.py`, `b/domain/conversation/lang/te.py`, `en.py`, `hi.py`, `ur.py` | Built |
| FR-15 | The language model may phrase the explanation using only the engine's facts. With no model key, the checked template is used. | `b/services/llm.py`, `b/flows/bill.py` | Built |
| FR-16 | Number guard: extract every number from the model's text (Telugu, Devanagari and Urdu digits included). If any number is not in the engine's facts or a small fixed list (such as 1912, 200), reject the text and use the template. | `b/domain/conversation/guard.py` | Built |
| FR-17 | Voice out: send the explanation as a voice note with Sarvam Bulbul in Telugu, English or Hindi. Split long text into chunks. Cache audio by text so repeats cost nothing. If voice fails, send text. | `b/services/tts.py`, `b/flows/turn.py` | Built (needs key) |
| FR-18 | Voice in: transcribe a voice question with Soniox, detect the language, switch the reply language, and reply with voice and text. | `b/services/stt.py`, `b/core/service.py` | Built (needs key) |
| FR-19 | Summary card under the voice note: audit status, units and group, amount to pay, due date, next month estimate. | `b/domain/conversation/composer.py` (`summary_card`) | Built |
| FR-20 | Prediction: estimate next month as a range and an amount. History is the usage table printed on the bill plus the account's own earlier uploads for the same service number. Use the same month last year adjusted for recent trend when 6 or more months exist; otherwise use this bill and a seasonal factor. | `b/domain/prediction.py`, `b/store/history.py` | Built |
| FR-21 | Slab warnings: if the estimate is likely to cross 100 or 200 units, warn. For Gruha Jyothi homes, warn that crossing 200 loses the free supply. | `b/domain/prediction.py`, `b/domain/conversation/composer.py` | Built |
| FR-22 | Savings: only when the cut needed to get back under 100 or 200 is at most a fifth of use, show how many units to cut, the rupee saving, and the same as AC minutes per day (1.5 kWh per hour) and geyser minutes. | `b/domain/insights.py` (`saving`) | Built |
| FR-23 | What-if: answer "what if I use N units" with the engine's amount. Build the bill curve and the jump at 100 and 200 units. | `b/domain/insights.py`, `b/flows/question.py` | Built |
| FR-24 | Gruha Jyothi: apply full subsidy for eligible homes at or under 200 units. Explain the subsidy, or explain that it was lost above 200 and how to get it back. | `b/domain/tariff/engine.py`, `b/domain/conversation/composer.py` | Built |
| FR-25 | Fixed intent list for questions: why_high, next_bill, save, complain, explain_fsa, explain_fixed, explain_customer, explain_duty, explain_true_up, gruha_jyothi, due, what_if, greeting, thanks, power_cut, new_connection, help, stop, off_topic. Keyword rules in four languages first; the model may pick only from this list. Answers are templates filled with engine figures. | `b/domain/conversation/intents.py`, `b/flows/question.py`, `b/services/llm.py` | Built |
| FR-26 | Out-of-scope requests (power cuts, new connections, other topics) get a fixed reply that points to 1912 or back to the bill. | `b/flows/question.py`, language packs | Built |
| FR-27 | Privacy notice on first WhatsApp contact and at registration. The version is set by `PRIVACY_NOTICE_VERSION`. | `b/flows/question.py`, `b/api/auth.py`, `b/config.py` | Built |
| FR-28 | STOP (or the word for it in Telugu, Hindi or Urdu) and account deletion erase the user's bills, chat and media no complaint refers to. A retention job removes data older than `RETENTION_DAYS` (180 by default). | `b/flows/question.py`, `b/store/repos.py` (`forget_user`), `b/api/auth.py` | Built |
| FR-29 | Complaint preview: show masked service number, bill month and the issue in the consumer's language, with Send and Cancel buttons. Nothing is filed without Send. | `b/flows/complaint.py` (`preview`) | Built |
| FR-30 | Complaint filing from the chat or the dashboard: create ticket `BM-yymmdd-NNNNN` with the audit lines in English, the overcharge amount and the bill photo. Recorded in Bill Mitra, not connected to 1912; the consumer is told to also call 1912. Statuses Open, In progress, Resolved, Rejected. | `b/flows/complaint.py`, `b/api/complaints.py`, `b/store/complaints.py` | Built |
| FR-31 | WhatsApp limits enforced in the message model: up to 3 reply buttons with 20-character titles, list rows up to 10 with 24-character titles, 1024 characters for interactive body text, 4096 for plain text. | `b/core/messages.py` | Built |
| FR-32 | WhatsApp Cloud API adapter: webhook verify, signature check (HMAC SHA-256), parse text, image, document, audio and button replies, download media, upload media, send replies. Switches on when token, phone number id and verify token are set. | `b/channels/whatsapp/router.py`, `mapper.py`, `client.py`, `b/config.py` | Built (needs number) |
| FR-33 | Web chat channel (Assistant): same engine, replies stream as they are ready. Phone UI with upload, voice recorder and language choice. | `b/channels/web.py`, `f/assistant/` | Built |
| FR-34 | "Behind the reply" trace panel: each step with its kind (rules, AI, channel), a note, and whether it was skipped. | `b/core/trace.py`, `f/assistant/components/TracePanel.tsx` | Built |
| FR-35 | Department console with real metrics only: reads trusted first time, re-read rescues, retakes, explanation number check pass rate, latency, complaints by status, overdue over 7 days. Date range and DISCOM filters. | `b/api/console.py`, `b/store/console.py`, `f/console/` | Built |
| FR-36 | Complaints inbox for officers: paged list in the URL, thread, reply and status change. Replies reach the consumer on WhatsApp (free text inside the 24 hour window, else the approved template in `WHATSAPP_COMPLAINT_TEMPLATE`, else recorded as failed with the reason) or in the web app. CSV export. | `b/api/complaints.py`, `b/services/notify.py`, `f/console/`, `f/complaints/` | Built |
| FR-37 | Tariff explorer: pick units, month, load and Gruha Jyothi; see slab lines, every charge, the bill curve and the jumps at 100 and 200. Uses the same engine as the assistant. | `b/api/catalog.py` (`/api/tariffs/calculate`), `f/explorer/` | Built |
| FR-38 | Provider status: health endpoint reports vision, language model, voice, listening and WhatsApp as live, template, off or connected. Shown on the How it works page. | `b/api/catalog.py` (`/api/health`), `f/explorer/components/WhatsAppReadiness.tsx` | Built |
| FR-39 | Bill dashboard: upload, then the full report with captured fields, consistency checks, charges check, slab breakdown reconciling to the printed total, history, next month and the plain explanation. Paged list of past bills. | `b/api/bills.py`, `b/flows/report.py`, `b/domain/capture.py`, `f/dashboard/` | Built |
| FR-40 | Event log for the console: bill read, question, alert, meter read and complaint, with language, intent, audit status, units, DISCOM and section. No personal data. | `b/store/repos.py` (`log_event`) | Built |
| FR-41 | Accounts and roles: sign in, consumer registration with mobile and password, roles admin, officer (optionally one DISCOM) and consumer. Server-side sessions, lockout after 5 wrong passwords. | `b/api/auth.py`, `b/store/accounts.py`, `b/core/security.py`, `f/auth/` | Built |
| FR-42 | Admin: create staff accounts, edit, deactivate, reset password, and read the audit log of admin and complaint actions. | `b/api/admin.py`, `b/store/accounts.py`, `f/admin/` | Built |
| FR-43 | My complaints for consumers: list, thread, reply. Delete my account. | `b/api/complaints.py`, `b/api/auth.py`, `f/complaints/` | Built |

## 7. Non-functional requirements

### Privacy

- The vision prompt tells the model not to read name, address or phone number. Only billing fields are extracted.
- Service numbers are masked to the last 4 digits wherever shown: complaint preview, console, trace.
- The WhatsApp user key is a SHA-256 hash of the number. The raw number is stored only on a complaint, so an officer's reply can be sent. It is never returned by the API or written to logs.
- A privacy notice is shown on first WhatsApp contact and at registration, in line with the DPDP Act 2023. History comes only from what the consumer gave us; nothing is fetched from the DISCOM.
- STOP and account deletion erase bills, chat and media that no complaint refers to. A retention job removes data after `RETENTION_DAYS` (180 by default). Complaint tickets and anonymous events stay for the record.
- The console works on counts and masked numbers only.

### Security

- Server-side sessions in an httpOnly, SameSite=Lax cookie that lasts 12 hours. Passwords hashed with scrypt. Five wrong passwords lock the login.
- Rate limits per address on login, register and uploads. Origin check on every write. Security headers (CSP, nosniff, frame options, HSTS when `COOKIE_SECURE` is on).
- Audit log of admin and complaint actions.
- WhatsApp webhook signature check and dedupe by message id.

### Reliability

- Every provider is optional. Without a key, the step is skipped and noted in the trace, and the consumer still gets a reply.
- Vision down or no key: ask for typed units. Rate limits from the provider are retried with back-off.
- Language model down or guard fails: use the checked template.
- Voice down: send text.
- Any unexpected error: a short apology in the consumer's language. The turn never ends in silence.
- Voice notes are cached on disk by text, so a repeat costs nothing.

### Latency

- Replies stream message by message, so the consumer sees progress.
- Provider calls time out at 45 seconds.
- Proposed pilot target: first reply in under 20 seconds for 9 in 10 bills. To be measured in the pilot.

### Languages

- Telugu is the default. English, Hindi and Urdu are supported for text.
- Voice out in Telugu, English and Hindi. Urdu is text only, with a note that voice comes later.
- The language switches automatically when a WhatsApp message arrives in Telugu, Hindi or Urdu script, or when a voice note is detected in one of these.
- Urdu text is shown right to left.

### Accessibility

- Voice first, for people who cannot read well.
- Buttons for the next step, so typing is rarely needed.
- Savings shown as AC minutes per day, not kWh.
- Short sentences and simple words in every language pack.

## 8. Edge cases handled

| Case | What Bill Mitra does |
|---|---|
| Blurry, tilted or cut off photo | If the rule checks fail after a second read, asks for a retake and says why. No guess. |
| Not a bill | Stopped at the first look. Says it does not look like an electricity bill and asks for a TGSPDCL or TGNPDCL bill. |
| Tall thermal spot-billing slip | Read in overlapping crops so small print stays legible. |
| Multi-page PDF | Up to 3 pages; the page that is a bill is read. |
| Shop or other non-domestic bill | Reads and explains it, marks it "not checkable", points to 1912. |
| Free Gruha Jyothi bill (Rs 0) | Applies the subsidy, says how much was saved, warns if next month is heading over 200. |
| Arrears on the bill | Separates arrears from this month's charges and states both. |
| Net metering (export units) | Bills on net units and explains the export. |
| Total-only SMS | A total without a breakdown can confirm a bill but never accuse it. If the total differs, status is "partial", never "mismatch". |
| Rounding | Differences up to Rs 1 per line count as a match. |
| Old tariff year | Checked against the tariff version in force in the bill month, for example March 2024 against FY2023-24. |
| True-up line | Explained as an approved charge, not audited. If it appears before November 2026, the audit records a note for review. |
| Meter photo with no earlier bill | Asks for the bill first, since the projection needs the last reading and date. |
| SMS that cannot be read | Asks for a photo or typed units. |
| Unsupported file type | Checked from the file bytes. Refused with HTTP 415 and a plain message: send a photo, PDF or voice note. |
| File too large | Refused with HTTP 413 above 12 MB. |
| Microphone permission refused | The voice button shows "Microphone permission was refused". Typing still works. |
| Question before any bill | Asks the consumer to send the bill first. |
| Provider down | Falls back as described in section 7. The trace shows what was skipped. |

## 9. Open items and assumptions

### Tariff items to confirm with the DISCOM

These are marked `verify` in the tariff tables. They are working assumptions until the DISCOM billing team confirms them.

| Item | Value used | Note |
|---|---|---|
| Domestic slabs FY2023-24 to FY2026-27 | Same in all four years. LT-I(A) up to 100 units: 0 to 50 at Rs 1.95, 51 to 100 at Rs 3.10. LT-I(B) up to 200 units: 0 to 100 at Rs 3.40, 101 to 200 at Rs 4.80. LT-I(C) above 200, telescopic: up to 200 at Rs 5.10, 201 to 300 at Rs 7.70, 301 to 400 at Rs 9.00, 401 to 800 at Rs 9.50, above 800 at Rs 10.00. | From the TGERC orders. |
| Slab pro-rating | Slab limits scaled by billing days divided by the days in the month the period started | Not in the schedule. Inferred from two real TGSPDCL bills, which the engine reproduces to the paisa. Marked `verify`. |
| FSA | Rs 0 per unit by default, set per month | Marked `verify`. Need monthly values from the DISCOM. |
| Customer charges FY2024-25 | Same as the schedule for the other years | Marked `verify` for this year only. |
| True-up | From November 2026: Rs 0.30 per unit in the first month, Rs 0.50 after | To confirm rates, start month and end month. |

Customer charges come from the TGERC schedule: Rs 40, 70, 90, 100, 120, 140 and 160 for up to 50, 100, 200, 300, 400, 800 and above 800 units. Duty is Rs 0.06 per unit and the fixed charge is Rs 10 per kW. Both real bills match these.

### Provider details not yet verified

- Sarvam: model `bulbul:v3`, speaker `kavya`. The API field for language has changed between versions, so the code tries `target_language_code` and then `language_code`. To verify with a live key.
- Soniox: model `stt-async-v5`. To verify with a live key.
- Azure OpenAI: `gpt-4.1` for reading bills (300k tokens per minute capacity) and `gpt-4.1-mini` for text. To review for data residency.

### Reading accuracy so far

Two real TGSPDCL slips (March 2024 and October 2025) are read 100 percent correct. We made 22 degraded phone-style versions of them (blur, motion, tilt, low light, glare, WhatsApp compression, cut off, and combinations). 15 were read correctly and the other 7 were asked to retake. None was trusted and wrong. Two non-bill images were stopped at the first look. Two bills is a small set; the pilot needs many more.

### Known gaps in this build

- No 1912 or DISCOM billing API integration.
- No SMS OTP for consumer sign up. It needs an SMS gateway.
- One API process (SQLite and in-memory rate limits), so no horizontal scaling yet.
- Media ids cannot be guessed, but any signed-in account could fetch a media file if it had the id.
- Complaints cannot be assigned to a named officer yet, and there is no SLA escalation.
- A Docker setup exists. An HTTPS proxy and backups are deployment work still to do.
- Urdu voice is not available.
- Gruha Jyothi eligibility comes only from what the bill prints.

### What we need

- A WhatsApp Business number, verified, with message templates approved.
- Cloud credits, or space on the state cloud, to host the pilot.
- DISCOM billing API (read only) for 12-month history and Gruha Jyothi eligibility, with the consumer's agreement.
- 1912 grievance API to file tickets and read status.
- TGERC tariff tables and monthly FSA in machine-readable form.
- An SMS gateway for sign up OTP.
- A larger set of real bills with manual checks, to measure reading and audit accuracy.

## 10. Milestones

| Date | Milestone |
|---|---|
| 16 Oct 2026 | Immersion Day jury session at IIIT Hyderabad. Live demo of this build. |
| 24 Oct 2026 | 15 finalists announced. |
| 25 Oct 2026 | Final deck and demo locked. |
| After the finals | Paid pilot with TGSPDCL or TGNPDCL in one circle, for example Kukatpally (TGSPDCL). |
| Pilot month 1 | WhatsApp number live, tariff items confirmed, DISCOM history API and 1912 API connected |
| Pilot month 2 to 3 | Measure the section 3 targets. Weekly review with the circle team. Add Urdu voice if a voice is available. |
| Incubation (12 months, CIE IIIT-H) | Extend to more circles and to TGNPDCL. Add non-domestic audit and proactive mid-month reminders. |

Prize pool for the challenge: Rs 36 lakh, a paid pilot with TGSPDCL or TGNPDCL, and 12 months of incubation at CIE IIIT-H.

---

Owner: Meraj Akhtar, AI Planet (meraj@aiplanet.com). Draft for the Immersion Day, 16 October 2026.
