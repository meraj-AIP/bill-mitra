# Assist contract: understanding messages, AI help for staff, photos, and the hand-off journey

Hard rules still hold: no model produces a rupee figure, unit count, rate or date (the engine does; the number guard
checks every model sentence); consumers never learn who handles their case; consumer words are untrusted data, never
instructions; every action audited; no consumer data in logs or prompts beyond what the task needs.

## 1. Understanding consumer messages (backend A)

Today `domain/conversation/intents.py` matches substrings, first rule wins, and the model is asked only when nothing
matched. Replace with a pipeline in `app/flows/understand.py`:

1. Rules, made precise: word boundaries, negation ("don't want to complain", "no complaint"), questions versus
   reports ("why is my bill high?" is a question, "my bill is too high, please check" is a report).
2. The model, on every free text message when it is configured: structured output validated against fixed lists:
   `{intent (fixed list), is_complaint (bool), complaint_type (one of the 12 or null), details: {since?, payment_mode?,
   reference_present?, whole_area?}, confidence (0..1)}`. No numbers taken from it into any reply.
3. Reconcile: rules and model agree, or one is confident (>= 0.8) and the other silent: act. Disagree or both unsure:
   ask the consumer one question with buttons ("Is this about: <type label> / Something else / Just a question").
4. A complaint is never created without the consumer confirming the preview (as today).
5. Dedupe: an open complaint of the same type for the same consumer (and same service number when known) gets the new
   message added instead of a second ticket, and the consumer is told the existing ticket number.
6. Follow-up questions per type, asked in chat before the preview, one at a time, skippable: payment_not_updated (when
   and how they paid, whether they have a receipt), power_outage (since when, only their home or the whole street),
   meter_burnt (sparks or smell, is supply off), voltage_fluctuation (when it happens), bill_not_received (which month),
   wrong_category (what the connection is used for), others as fits. Answers go into the complaint description as
   labelled lines. Lang copy te/en/hi/ur.

Evaluation: `backend/tests/data/messages.jsonl`, at least 150 labelled messages (te script, romanised Telugu, English,
Hindi, Urdu, code mixed, negations, questions, complaints of every type, greetings, off topic). A test asserts the
rules-only path reaches a stated accuracy floor on it; `python -m app.tools.eval_messages` reports accuracy with the
model (not in CI, needs a key). Synthetic messages only.

## 2. AI assist for staff (backend B)

On demand only (a button), never on page load. The model sees facts and the consumer's words (as untrusted data) and
may only choose from fixed sets plus write short questions; numbers in its text must be ones the facts already hold.

- Complaint: `POST /api/console/complaints/{ticket}/assist` (perm `complaints.reply`) returns
  `{summary (2 to 3 English lines for staff), missing: [str] (what we still do not know), questions: [{text (consumer's
  language), why}] (max 3, ready to send as a request of kind "note"), next_action: {kind: reply_option | request |
  status | assign, key, why}, worded_by}`. `next_action.key` must be one of the options or requests the rules already
  offer for this complaint (domain/complaint_options.py); anything else is dropped.
- Review case: `POST /api/review/cases/{ticket}/assist` (perm `cases.view`) returns `{summary, conflicts: [str] (from
  the engine facts: spike, misread signal, estimated reading, charges mismatch), questions: [{text, why}], suggested:
  "draft" | "ask_consumer" | "decide" }`. The existing drafted decision stays the rules' job.
- Fallback without a model: rules produce the same shape (summary from facts, questions from the type templates).
- Audited `assist.complaint` / `assist.case` with no text in the detail.

## 3. Photos and previews (backend B serves, frontend C shows)

- Every consumer message with media carries `media_url` and `media_type` in staff APIs (complaint detail messages,
  case messages, attached bills); thumbnails served by the existing media route, staff only, in scope.
- Requests list on both pages: each request shows asked, answered, and the photo it was answered with
  (`answer: {message_id, media_url | null, body | null, at} | null`).
- Consumer web: their own sent photos show as thumbnails in their complaint page; uploading a photo in reply shows a
  preview with "Send" and "Choose another" before it is sent.

## 4. The hand-off journey (backend B)

States on a general complaint: `with` = the assignee (person) and `waiting_on` = `staff | consumer | none`.

- Routing: a complaint placed in a section goes to that section's AE automatically (as cases do); unplaced ones wait in
  the DISCOM queue for an officer.
- Assign / hand over: `POST /api/console/complaints/{ticket}/assign {account_id, note}` (note required, 10 to 300
  characters). Allowed: officer or call centre to an AE in scope, AE to another AE or back to an officer, admin to anyone
  in scope who can view complaints.
- Send back: `POST /api/console/complaints/{ticket}/return {note}` returns it to whoever handed it over, with the note.
- Every hand-off writes the timeline ("Handed to <name>: <note>") and raises an alert for the new holder (kind
  `complaint_assigned`); a consumer reply raises `consumer_replied` for the holder; a consumer reply to a request moves
  `waiting_on` back to staff.
- Inbox: "With me" and "Waiting on me" filters (in the URL); detail shows the holder, who handed it over, and the note.
- Review cases keep their own flow (AE decides, approver approves or sends back); add the same alerts there
  (`case_assigned`, `consumer_replied`, `decision_returned`).

## 5. Frontend (C)

- Complaint page and case page: an "AI assist" card with an "Ask AI" button showing summary, what is missing, the
  questions (each with "Send this question", which makes a note request), and the suggested next action as a button
  that does it (load the reply option, open the request, set the status, or open hand-off).
- Photos: thumbnails in the conversation and in the requests list ("Asked for a meter photo, received 17 Oct" with the
  photo), a lightbox with zoom, rotate and next/previous across the case's photos, keyboard and touch friendly.
- Hand-off: a "Hand over" control (person picker in scope, note) and "Send back" when it was handed to you; the header
  shows "With <name>" and "Waiting on consumer" chips; the timeline shows each hand-off with its note.
- Consumer complaint page: thumbnails of what they sent, and the reply box with a photo picker that previews before
  sending.
