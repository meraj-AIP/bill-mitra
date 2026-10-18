# Bill Mitra

Bill Mitra is AI Planet's entry for the Telangana Department of Energy EnergyTech Innovation Challenge (Personalized Billing Assistance, Agentic AI).
A consumer sends a photo of the electricity bill on WhatsApp. Bill Mitra reads it, checks every line against the TGERC tariff with a rule engine, explains it in Telugu as a voice note and text, and predicts next month's bill.
If the bill looks wrong, the consumer reports it with one tap. The case goes to the section office with an evidence pack already built, and an approved revision becomes the bill for that month.
This repo is a web app with sign in and role-based access: a bill dashboard and a WhatsApp preview chat for consumers; the console, complaints inbox and review queue for DISCOM staff; roles, units, review policy and accounts for the admin. There is no mock or sample data anywhere.
Rules calculate, AI explains: no rupee figure ever comes from a language model, revised amounts included.

## Run it

You need Python 3.11+ and Node 22.

```bash
cp .env.example .env    # set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD
./run.sh
```

Open http://localhost:8000. The first run creates `backend/.venv`, installs packages and builds the web app. After that it starts in a few seconds.

Sign in. The first admin is created at startup from `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` in `.env`, only when no admin exists. Change that password after the first login. Consumers register themselves in the app with a mobile number and password.

## Roles and access

Access is by permission, and every staff account has a role plus one or more units it covers (a DISCOM, circle, division, subdivision, section or ERO). The built-in roles are admin, DISCOM officer, section AE, call centre agent, billing approver, auditor and consumer. An admin can edit the built-in staff roles (not the consumer role), reset them to their defaults and create custom roles. Nobody approves or applies their own decision, and the admin role holds no money permissions.

First steps as admin: add the units under Manage, Units (or import a CSV), then create staff accounts with a role and their units. Bill sections are matched to section units by name or alias; a name nobody has mapped shows in the unmapped queue.

## Bill review in short

1. The consumer taps "Bill looks wrong" in the chat, or "Report a problem with this bill" on the web bill page. The consumer only sees neutral states and the DISCOM's name, never who checks.
2. The case is routed to the section AE by the section printed on the bill. An evidence pack is built at once, and if any of the 3 months before the bill month are missing, the consumer is asked for those bills.
3. The AE marks the bill correct, enters a corrected reading (the engine reprices it) or a custom reduction, with a reason, a note and evidence. By default the AE decides alone; a DISCOM can require a second approval.
4. The revised amount becomes the consumer's bill. A billing approver marks it applied once the DISCOM system is updated. Every step is on the case timeline and in the audit log.

The full rules are in [docs/review-contract.md](docs/review-contract.md).

With Docker:

```bash
cp .env.example .env
docker compose up --build
```

Dev mode (API with reload on 8000, Vite on 5173 with `/api` proxied to 8000; keep `http://localhost:5173` in `CORS_ORIGINS`):

```bash
./run.sh dev
```

Then open http://localhost:5173. A consumer lands on the Dashboard; the WhatsApp preview is at `/assistant`.

## Demo script

About seven minutes for the jury. The presenter brings two or three real bill photos (or PDFs) on a phone or laptop. Have a section AE and an officer account ready, scoped on the section printed on the demo bill.

1. **Read and check, in Telugu.** Register as a consumer (or sign in). On the Dashboard (Telugu is the default) upload a bill. While it reads, the page shows each stage. Then walk the report: the bill next to the result, "Captured N of M fields", the line by line charges check and the plain Telugu explanation.
2. **History and next month.** Scroll to the usage chart (from the table printed on the bill and any earlier upload) and next month's estimate with the saving tip. Switch the explanation to English.
3. **A bad photo.** Upload a blurry or tilted photo, or something that is not a bill. Bill Mitra says what it saw and asks for a retake, with tips.
4. **Ask on WhatsApp.** Tap "Ask about this bill" to open the Assistant. Send the same photo, then type `what if 230 units?`. The rule engine prices it and the assistant explains the result, with a voice note.
5. **Bill looks wrong.** On the bill page, tap "Report a problem with this bill". The consumer sees "received" and, if months are missing, a request for earlier bills. Upload one of them and it joins the case.
6. **Section AE.** Sign in as a section AE. Open the case in Review: bill, readings, evidence pack and timeline on one page. Enter a corrected reading, check the engine's preview and record the decision. Back as the consumer, the bill now shows the revised amount next to the original.
7. **Officer.** Sign in as an officer. The Console shows the bills just read (trusted first time, re-reads, retakes). Open a complaint raised in the chat, reply and set it In progress. Complaints are recorded in Bill Mitra only, not in 1912.
8. **How it works.** Play the journeys on the system map: a consumer sends a bill, and, as staff, a wrong bill reviewed and an admin changing a role.

## Provider keys

Without a key that part is switched off and the app says so. Nothing is ever faked.

| Setting | With the key | Without it |
| --- | --- | --- |
| `OPENAI_API_KEY` | Reads any bill photo with `gpt-4.1`, writes explanations with `gpt-4.1-mini` | Bill reading is off: the consumer types the units instead. Explanations come from the checked templates |
| `SARVAM_API_KEY` | Telugu voice notes with Sarvam `bulbul:v3` | Text only, no voice |
| `SONIOX_API_KEY` | Voice questions transcribed with Soniox `stt-async-v5` | Typed questions only |
| `WHATSAPP_*` (four settings) | Real WhatsApp number through the Cloud API | Web chat only |
| `BILLING_RECORDS_URL`, `BILLING_RECORDS_TOKEN` | DISCOM billing history joins the review evidence pack | The pack says the DISCOM records are not connected. Nothing is fetched |

The rule engine, tariff tables, predictions, console, complaints and bill review work the same either way. We run the OpenAI models on Azure OpenAI through `OPENAI_BASE_URL`.

## Going live on WhatsApp

1. Create a Meta Business account and an app with the WhatsApp product added.
2. Add and verify a phone number in WhatsApp Manager. Note its phone number id.
3. Set these in `.env`:
   - `WHATSAPP_TOKEN`: a permanent system user access token
   - `WHATSAPP_PHONE_NUMBER_ID`: from step 2
   - `WHATSAPP_VERIFY_TOKEN`: any string you choose
   - `WHATSAPP_APP_SECRET`: from the app's basic settings, used to check webhook signatures
4. Run the app on a public HTTPS URL (a server, or a tunnel for testing).
5. In the app's WhatsApp configuration set the callback URL to `https://<your-host>/api/whatsapp/webhook` and the verify token to the same `WHATSAPP_VERIFY_TOKEN`. Meta calls the URL once to verify it.
6. Subscribe to the `messages` webhook field. Send a bill photo to the number.
7. To reach consumers outside WhatsApp's 24 hour window, get a complaint update template approved and put its name in `WHATSAPP_COMPLAINT_TEMPLATE`.

Install `ffmpeg` on the server (the Docker image has it) so voice replies show as WhatsApp voice notes.

Other settings worth knowing: `SESSION_COOKIE` (default `bm_session`; give each instance on one host its own name), `COMPLAINT_REPLY_DAYS` (default 7) and `WHATSAPP_DISPLAY_NUMBER` (for the dashboard's WhatsApp link). All settings are listed in `.env.example` and [ARCHITECTURE.md](ARCHITECTURE.md).

## Operations

Production runs in Docker on a shared VM at https://aikam.tryaiplanet.com. Backups, the health watchdog, the deploy
script, cron setup, restoring a backup and the GitHub Actions workflows (CI, uptime, deploy) are in
[deploy/README.md](deploy/README.md).

## Tests

```bash
cd backend && pip install -r requirements-dev.txt && pytest && ruff check .
cd frontend && npm run typecheck && npm run lint
```

The backend suite (about 210 tests) runs on two real bills with identifiers replaced. `tests/test_access_matrix.py` checks every built-in role against the protected areas, so a route that forgets its permission check fails there.

## Project layout

```
backend/
  app/
    api/            auth, admin, access (roles, units, policy), bills, complaints, review, console and catalog routes
    channels/       web and whatsapp adapters, both call core/service.handle
    core/           channel-neutral messages and the conversation service
    domain/
      tariff/       TGERC tariff tables and the rule engine
      conversation/ intents, facts, composer, number guard, language strings
      rbac.py       permission catalogue and built-in roles
      review.py     spike rules, decision pricing, final amounts
    flows/          bill, meter, question, complaint, report and bill review (cases, case_bills, evidence) flows
    services/       OpenAI, Sarvam and Soniox clients, complaint reply delivery, DISCOM billing records
    store/          storage (SQLite, or Postgres with DATABASE_URL): bills, accounts, complaints, cases
  tests/
frontend/src/
  app/              shell and routes
  features/         auth, dashboard, assistant, complaints, console, review, admin, explorer (How it works)
  shared/ theme/
docs/
```

## More docs

- [PRD.md](PRD.md): what we are building and why
- [ARCHITECTURE.md](ARCHITECTURE.md): how the pieces fit
- [docs/CONTEXT.md](docs/CONTEXT.md): challenge background and tariff notes
- [docs/api-contract.md](docs/api-contract.md): every route, with bodies and permissions
- [docs/review-contract.md](docs/review-contract.md): roles, units and the bill review rules
- [AGENTS.md](AGENTS.md): rules for anyone changing the code

Built by AI Planet. Contact: Meraj Akhtar, meraj@aiplanet.com. See [LICENSE](LICENSE).
