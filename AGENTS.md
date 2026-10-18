# Working on Bill Mitra

Rules for the next developer or coding agent. Read these before you change anything.
Setup and run steps are in [README.md](README.md).

## The one rule: rules calculate, AI explains

- No language model ever produces a rupee figure, unit count, rate or date. Every number comes from the rule engine in `backend/app/domain/tariff/engine.py`.
- The model only puts engine facts into plain words. Pass it facts, never ask it to compute.
- The number guard in `backend/app/domain/conversation/guard.py` must stay. It rejects any model answer that has a number the engine did not produce and falls back to the template answer. Do not remove it, weaken it or route around it. If a new answer needs a new number, add it to the facts first.
- Bill reading (vision) can extract numbers from the photo, but they are checked by the engine before anyone sees them.

## Messages are WhatsApp messages

- Every outbound message must be a WhatsApp Cloud API type, built with the models in `backend/app/core/messages.py`.
- Limits are enforced there, not in the channels: reply buttons max 3 with 20 character titles, list rows max 10 with 24 character titles, interactive body text max 1024 characters.
- The web demo renders the same messages. If something cannot be sent on WhatsApp, it does not go in the web demo either.

## Channels

- A new channel is a new adapter under `backend/app/channels/` that maps its input to `Inbound` and calls `core/service.handle`.
- Business logic never lives in an adapter. Adapters translate, nothing more.

## Tariffs

- Tariff data lives in `backend/app/domain/tariff/tables.py`.
- A new TGERC order is added as a new version with its effective dates. Never edit an old version: old bills must keep being checked against the tariff that was in force in their bill month.
- Rates marked `verify=True` are assumptions until the DISCOM billing team confirms them.
- Add a test in `backend/tests/test_tariff.py` for every new version.

## Languages

- All user facing strings live in `backend/app/domain/conversation/lang/` (one file per language: `te`, `en`, `hi`, `ur`). No hard coded copy in flows or adapters.
- Telugu is the first language. Write it as people speak, not as a literal translation.

## Frontend

- Feature sliced: `src/features/<feature>/{api,components,hooks,model,routes}`.
- Import from another feature only through its `index.ts`. Use the `@/` alias, no deep relative paths across features.
- MUI v9 with the `sx` prop only. No CSS files, no styled wrappers for one off styles.
- Use theme tokens (`primary.main`, `text.secondary`, spacing units). No hex colours in components.
- Lists and tables use server side pagination, with page, filters and sort kept in the URL.
- Keep every file under 300 lines. Split it before it gets there.
- `npm run typecheck` and `npm run lint` must pass with zero warnings.

## Backend

- Python 3.11+, FastAPI. SQLite by default, Postgres when `DATABASE_URL` is set. Settings only through `backend/app/config.py`.
- SQL is written once, in SQLite's dialect, and must run on both (docs/decisions/0001-postgres-store.md). Compare
  flags with `= 1`, never use a comparison as a number, and read a `RETURNING` row inside the transaction. Run the
  suite on Postgres too: `TEST_DATABASE_URL=postgresql://.../scratch_db pytest` (the suite wipes that database).
- No secrets in code, tests or fixtures. No consumer data (names, service numbers, phone numbers) in logs.
- `pytest` and `ruff check .` must pass before you commit.

## Writing and commits

- Commits are authored as `Meraj Akhtar <meraj@aiplanet.com>`.
- No AI attribution anywhere: not in code comments, commit messages, PR text or docs.
- Never use em dashes or en dashes in any copy, comment or doc. Use commas, colons, full stops or brackets.
- Plain, short sentences. Comments say why, not what.
