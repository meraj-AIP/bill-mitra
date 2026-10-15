# Bill Mitra

Bill Mitra is AI Planet's entry for the Telangana Department of Energy EnergyTech Innovation Challenge (Personalized Billing Assistance, Agentic AI).
A consumer sends a photo of the electricity bill on WhatsApp. Bill Mitra reads it, checks every line against the TGERC tariff with a rule engine, explains it in Telugu as a voice note and text, and predicts next month's bill.
This repo is a web app with sign in: a bill dashboard and a WhatsApp preview chat for consumers, a Department console and complaints inbox for officers, and account management for admins. There is no mock or sample data anywhere.
Rules calculate, AI explains: no rupee figure ever comes from a language model.

## Run it

You need Python 3.11+ and Node 22.

```bash
cp .env.example .env    # set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD
./run.sh
```

Open http://localhost:8000. The first run creates `backend/.venv`, installs packages and builds the web app. After that it starts in a few seconds.

Sign in. The first admin is created at startup from `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` in `.env`, only when no admin exists. Change that password after the first login. The admin creates officer accounts. Consumers register themselves in the app with a mobile number and password.

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

About five minutes for the jury. The presenter brings two or three real bill photos (or PDFs) on a phone or laptop. Have an officer account ready.

1. **Read and check, in Telugu.** Register as a consumer (or sign in). On the Dashboard (Telugu is the default) upload a bill. While it reads, the page shows each stage. Then walk the report: the bill next to the result, "Captured N of M fields", the line by line charges check and the plain Telugu explanation.
2. **History and next month.** Scroll to the usage chart (from the table printed on the bill and any earlier upload) and next month's estimate with the saving tip. Switch the explanation to English.
3. **A bad photo.** Upload a blurry or tilted photo, or something that is not a bill. Bill Mitra says what it saw and asks for a retake, with tips.
4. **Ask on WhatsApp.** Tap "Ask about this bill" to open the Assistant. Send the same photo, then type `what if 230 units?`. The rule engine prices it and the assistant explains the result, with a voice note.
5. **Complaint.** Raise a complaint on the bill. It gets a `BM-` ticket. It is recorded in Bill Mitra only, not in 1912, and the consumer is told to also call 1912.
6. **Officer.** Sign in as the officer. The Console shows the bills just read (trusted first time, re-reads, retakes). Open the complaint in the inbox, reply and set it In progress. Back as the consumer, the reply is under My complaints.
7. **How it works.** Walk through the flow: read, check, explain, predict, and why the AI never makes up a number.

## Provider keys

Without a key that part is switched off and the app says so. Nothing is ever faked.

| Setting | With the key | Without it |
| --- | --- | --- |
| `OPENAI_API_KEY` | Reads any bill photo with `gpt-4.1`, writes explanations with `gpt-4.1-mini` | Bill reading is off: the consumer types the units instead. Explanations come from the checked templates |
| `SARVAM_API_KEY` | Telugu voice notes with Sarvam `bulbul:v3` | Text only, no voice |
| `SONIOX_API_KEY` | Voice questions transcribed with Soniox `stt-async-v5` | Typed questions only |
| `WHATSAPP_*` (four settings) | Real WhatsApp number through the Cloud API | Web chat only |

The rule engine, tariff tables, predictions, console and complaints work the same either way. We run the OpenAI models on Azure OpenAI through `OPENAI_BASE_URL`.

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

## Tests

```bash
cd backend && pip install -r requirements-dev.txt && pytest && ruff check .
cd frontend && npm run typecheck && npm run lint
```

## Project layout

```
backend/
  app/
    api/            auth, admin, bills, complaints, console and catalog routes
    channels/       web and whatsapp adapters, both call core/service.handle
    core/           channel-neutral messages and the conversation service
    domain/
      tariff/       TGERC tariff tables and the rule engine
      conversation/ intents, facts, composer, number guard, language strings
    flows/          bill, meter, question, complaint and report flows
    services/       OpenAI, Sarvam and Soniox clients, complaint reply delivery
    store/          SQLite storage: bills, accounts, complaints, history
  tests/
frontend/src/
  app/              shell and routes
  features/         auth, dashboard, assistant, complaints, console, admin, explorer (How it works)
  shared/ theme/
docs/
```

## More docs

- [PRD.md](PRD.md): what we are building and why
- [ARCHITECTURE.md](ARCHITECTURE.md): how the pieces fit
- [docs/CONTEXT.md](docs/CONTEXT.md): challenge background and tariff notes
- [docs/api-contract.md](docs/api-contract.md): the API for accounts, admin and complaints
- [AGENTS.md](AGENTS.md): rules for anyone changing the code

Built by AI Planet. Contact: Meraj Akhtar, meraj@aiplanet.com. See [LICENSE](LICENSE).
