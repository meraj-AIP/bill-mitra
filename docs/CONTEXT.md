# Bill Mitra: project context

Owner: Meraj Akhtar, COO, AI Planet (DPhi Tech), meraj@aiplanet.com

This file holds the full background of Bill Mitra. Read it before you change anything. It covers the challenge, what we pitched, what we decided and why, and what is still open.

## 1. What this is

Bill Mitra is an electricity bill assistant for households in Telangana. It lives on WhatsApp.

A consumer sends a photo of the electricity bill. Bill Mitra reads it, explains every charge in Telugu (text and voice), checks the amount against the tariff, looks at usage and predicts the next bill. It can record a complaint, which a department officer answers. And when the reading itself looks wrong, the consumer taps "Bill looks wrong": the section AE reviews it with an evidence pack the system has already gathered, and an approved revision becomes the bill.

This repository is the working app. It has sign in with role-based access, a bill dashboard, a chat that looks and behaves like WhatsApp, a Department console, a complaints inbox, a bill review queue, and admin screens for roles, units, review policy and accounts. All of it runs on the same engine the WhatsApp version uses.

## 2. The challenge

- Name: EnergyTech Innovation Challenge, run by the Telangana Department of Energy.
- Problem statement: Personalized Billing Assistance (Agentic AI).
- Run with: AIKAM Global, IIIT Hyderabad and GDG Hyderabad.
- Contacts: Zaid bin Khalid (+91 77026 72041) and Ramya Sushanth.

Key dates:

| Date | What happens |
|---|---|
| Before 15 Oct 2026 | Submission sent and approved |
| 16 Oct 2026, 9:00 to 17:45 | Immersion Day, Solution/Demo Jury Session at IIIT Hyderabad. We are in the top 30. |
| 24 Oct 2026 | 15 finalists announced |
| 25 Oct 2026 | Final deck and demo lock |

Prizes:

- Rs 36 lakh prize pool.
- A paid pilot with TGSPDCL or TGNPDCL.
- 12 months of incubation at CIE IIIT-H.

## 3. What we submitted and pitched

The submission described Bill Mitra as a WhatsApp assistant. The consumer photographs the bill, and the assistant explains it in Telugu, checks it, analyses consumption and predicts the next bill.

We had not sent any AI Planet overview deck before. So the jury deck introduces the product first and keeps the company story short.

The jury deck:

- 12 main slides plus 3 backup slides.
- A "What we need" slide asking for cloud resources and API access.
- Cost sits in the backup slides only.
- Logos: AI Planet plus the Department of Energy and partner logos.
- The demo is not part of the deck. A recorded video is kept separate.

## 4. Timeline of this work

All of this was done in our working sessions in the days before the jury session.

1. Owner shared that the submission was approved and asked how to approach the jury presentation.
2. We agreed to go straight into the problem and the product, since no company deck had been sent before.
3. Planned the deck in detail and built a first version as slides. It ran to around 19 to 20 slides.
4. Owner asked to shrink it. Trimmed to 12 main slides plus 3 backup, and added the "What we need" slide for cloud (for example Azure) and API access.
5. Built the architecture diagram as PNG, SVG and PDF. It was made to look hand-drawn and plain, not like a generated graphic.
6. Built a PPTX version of the deck.
7. Owner shared the AIKAM shortlist email. We read it together: top 30, jury session on 16 Oct.
8. Owner shared his updated Google Slides deck (his own font and edits). We applied changes directly there: the cover subtitle now mentions Immersion Day at IIIT Hyderabad, page totals read /14, and the last slide reads 14/14.
9. Owner asked: what if the jury asks to see a demo?
10. We planned a demo app: a React web app that mimics WhatsApp, with mock upload, since there is no Meta or WhatsApp account yet.
11. Owner asked to build it end to end, cover every edge case, and keep the design simple. This repository is the result.
12. We then removed every made-up bill and figure, tested reading on two real TGSPDCL bills, and added sign in, roles, the complaints inbox and privacy controls.
13. After the jury session (16 to 17 Oct) we added role-based access with org units and scopes, and the AE bill review flow: report, routing, evidence pack, requests for earlier bills, decisions, final amounts and the case timeline. The admin can now edit built-in roles. The How it works page got playable journeys, including staff-only ones.

## 5. Decisions and why

| Decision | Reason |
|---|---|
| WhatsApp is the product and the pitch | Most households already use WhatsApp. No app to install. This is what we told the jury. |
| The web app comes first | We have no Meta Business account or WhatsApp number yet. The jury still needs to see it working, and officers need a place to answer complaints anyway. |
| The web chat shows only WhatsApp message types | Text, images, voice notes, up to 3 reply buttons, lists. If it works in the web chat, it works on WhatsApp. Web-only tools sit outside the phone frame. |
| WhatsApp adapter is built now, switched on later | It turns on once the WHATSAPP_* settings are filled in. No code change needed. |
| Sarvam for text to speech | Good Telugu voice. Owner's choice. |
| Soniox for speech to text | Owner already has a Soniox key and we use it on other work. |
| OpenAI for reading the bill photo and for wording | Strong at reading photos. Wording is checked by the rules (see below). |
| Rules calculate, AI explains | Every rupee comes from a fixed tariff engine. The AI only writes the words. A check rejects any reply with a number the engine did not produce, and we fall back to a safe template. |
| No mock data, ever | Early builds had made-up bills and console figures. We removed all of it. Without an OpenAI key, bill reading is off and the consumer types the units. Nothing is faked. |
| Two pass reading with rule checks | A misread bill must never be trusted. Readings, charges, total and billing days are checked; one re-read, then a retake with the reason. |
| Telugu first, then English, Hindi and Urdu | Telangana households. Urdu is text only, no voice. |
| Charts sent as images | WhatsApp cannot show live charts. |
| MUI design, simple and minimal | Same style as the owner's recent task app. Enterprise-plain, no flashy colours. |
| Logos: AI Planet and the AIKAM lockup | AIKAM lockup has the Telangana Government seal, Telangana Rising and aikam. |
| History mostly from what the consumer gives us; privacy notice; STOP and account deletion erase data | Privacy. History is the table printed on the bill plus the account's own uploads. DISCOM billing records are fetched only for a reported bill, and only once the DISCOM connects them (off today). We never read name, address or phone from the bill. |
| Department console and complaints inbox included | Shows the DISCOM what they get, from real activity only: reading quality, complaints by status, overdue tickets. Officers reply from the inbox. |
| Complaints recorded in Bill Mitra, not 1912 | We have no 1912 API access. Tickets are `BM-` numbers and the consumer is told to also call 1912. |
| Access by permission and unit, not by role name | DISCOMs run on circles, divisions and sections. Each staff account covers its units only. Roles are sets of permissions, so a DISCOM can shape its own roles. |
| Admin can edit built-in roles, with locks | Owner's call. The consumer role is locked, admin keeps role management, and role management never sits with money permissions. Edits survive a restart and can be reset. |
| Separation of duties | Nobody approves or applies their own decision. Admin never moves money. |
| Consumers never see who reviews | Owner's call. Consumer copy names only the DISCOM. No "AE" and no staff names on the consumer side. |
| AE decides alone by default | Owner's call. `ae_limit` is empty and custom reductions need no approval. A DISCOM can switch on a second approval in the review policy. |
| Evidence is gathered before the AE opens the case | The AE should not wait for basics. The pack is built on report, and missing earlier bills are asked for at once. |
| The original bill is never edited | A revision is a new numbered record. The revised amount is shown as the bill, with the original beside it. |
| Demo not in the deck | Owner's call. A recorded video is shared separately. |
| No GitHub URL for now | Owner said it is not needed at this stage. |

## 6. The owner's requirements for the demo

In his words, cleaned up and kept short:

- "What if they ask to see the demo? Can we have the application, maybe a React application?"
- "I don't have a Facebook ID or WhatsApp integrations done."
- "For TTS and STT, I can provide the API key for Soniox."
- "Let's make it world-class."
- "Cover all the edge cases and every functionality. Take that extra mile."
- "API keys at a later stage."
- "Let's go with Sarvam."
- "Use our MUI design, like how we did the task application recently. Keep things simple, minimalistic."
- "The end goal will be to integrate with WhatsApp. That is what we are going to pitch. We should not divert from the initial plan."
- "Put a prd.md and architecture.md in the project, so that we have the complete context."

## 7. What is real and what is not built

What is real:

- The tariff engine. Slabs follow the published TGERC domestic tariff for FY 2023-24 to FY 2026-27. It reproduces two real TGSPDCL bills to the paisa. Gruha Jyothi (free up to 200 units) is handled.
- Bill reading with rule checks. Two real TGSPDCL slips read 100 percent correct. Of 22 degraded phone-style copies, 15 were read correctly and 7 were asked to retake. None was trusted and wrong.
- The bill check, line by line, with a Rs 1 tolerance.
- The next bill prediction and the savings tips.
- The conversation flow, in four languages.
- Accounts, the console, the complaints inbox and officer replies.
- Role-based access: seven built-in roles, custom roles, admin role editing with reset, unit scopes, and a test that checks every built-in role against 14 protected areas.
- Org units with aliases, CSV import and the unmapped section queue.
- AE bill review: report, routing, evidence pack, automatic request for earlier bills, decisions priced by the engine, optional approval, revisions, final amounts and the case timeline.
- The WhatsApp adapter code (webhook check, signature check, dedupe, media upload and download).

What is not built or not live:

- WhatsApp is not connected. No Meta account or number yet.
- Complaints are recorded in Bill Mitra only. Nothing goes to 1912. Revisions are marked applied by hand with a billing reference; nothing is written to the DISCOM's billing system.
- DISCOM billing records connector is built but not connected. History and Gruha Jyothi eligibility come from the bill and earlier uploads.
- No real org tree or staff list loaded yet. No single sign on. No SLA alerts.
- No SMS OTP at sign up. One API process only, so no horizontal scaling yet.
- Urdu voice is not available.

## 8. Open items to verify before the pilot

| Item | Status |
|---|---|
| Electricity duty | Deck said 6 percent. Engine uses 6 paise per unit, which both real bills match. Fix the deck. |
| Slab pro-rating by billing days | Inferred from two real bills. Marked "verify". |
| Customer charges (Rs 40 to 160 by band) | From the TGERC schedule and matched by both real bills. FY 2024-25 still marked "verify". |
| FSA (fuel surcharge) | Set to 0 by default. Needs the real monthly figure. |
| True-up charge from Nov 2026 | Built in as Rs 0.30 then Rs 0.50 per unit. Confirm the rates. |
| Sarvam speaker "kavya" and the language field name | Not confirmed against live API. A fallback field exists. |
| Soniox model name "stt-async-v5" | Not confirmed against live API. |
| Azure OpenAI gpt-4.1 (vision) and gpt-4.1-mini (text) | In use. Review data residency before the pilot. |
| Deck slide 9 | Still has the "[__] engineers" placeholder. Fill before 25 Oct. |
| Adoption target in the deck | Ambitious. Be ready to defend it or soften it. |

## 9. Working rules for anyone continuing this

Writing:

- Never use em dashes or en dashes. Use commas, full stops, colons or brackets.
- Everything must read as written by our team. Plain, easy words. Short sentences.
- Keep reports short (one to two pages).
- No emoji.

Design:

- Enterprise-plain. No gradient palettes or decorative extras that look machine-made.
- Keep to the existing MUI theme (navy primary, green secondary, WhatsApp-style chat colours).

Code:

- Commits authored as Meraj Akhtar <meraj@aiplanet.com>. No co-author lines or tool attribution in commits, PRs or code.
- Never hardcode keys. All keys go in `.env` (see `.env.example`).
- Keep the rule: numbers come from the engine, words come from the AI, and the guard checks every number.
- Any new reply must fit WhatsApp limits: up to 3 buttons with titles of 20 characters or fewer, list rows of 24 characters or fewer, body of 1024 characters or fewer.
- Do not extract or store name, address or phone. WhatsApp numbers are stored only as a hashed key.
- Run backend tests (`pytest`, `ruff check .`) and the frontend typecheck, lint and build before calling anything done.
- Consumer copy never names who reviews a bill. Only the DISCOM.
- Never weaken a permission check or the separation of duties. `tests/test_access_matrix.py` must stay green.

Email:

- Never send mail from the owner's mailbox. Write drafts only. He sends them himself.

## 10. Next steps

After the 16 Oct jury session:

1. Collect more real bills, from both DISCOMs, and measure reading accuracy on them.
2. Confirm the open items in section 8, starting with FSA and billing-day pro-rating.
3. Record a short demo video on a real bill.
4. Fill the slide 9 placeholder and review the adoption target.
5. Prepare for 24 Oct (finalist list) and lock the final deck and demo by 25 Oct.
6. Set up a Meta Business account and a WhatsApp Business number. Fill the WHATSAPP_* settings and test the webhook end to end.
7. If we win the pilot: get real tariff and bill data from TGSPDCL or TGNPDCL, connect the billing records connector, load the real org tree and staff, and connect complaints to the DISCOM's own system.
