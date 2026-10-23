# Errors contract: every failure says what happened, which part, and what to do next

Rules that still hold: no model produces a number (the engine does, the guard checks), bill numbers reach a person
only after the capture checks or the consumer's own confirmation, consumers never see staff names, all copy in
te/en/hi/ur, no consumer data in logs.

## 1. Consumer messages (backend, lang packs)

Every failure message has three parts: what happened (plainly, never blaming the person), which part (the field or
check, using values printed on the bill), and what to do next, with buttons wherever WhatsApp allows (max 3, 20
characters). No message ends a conversation without a way forward.

- Capture check failures (`app/domain/capture.py`) each get their own message, built from the check's facts:
  - readings vs units: "Your bill shows readings {previous} to {present}, which is {difference} units, but it says
    {units} units." Buttons: "{difference} units", "{units} units", "New photo". The consumer's pick becomes the
    units and the engine prices it, marked as confirmed by the consumer.
  - energy charge implies different units: same pattern with the units the charge fits.
  - charges vs bill amount, bill amount plus arrears vs total, net/export units: say which totals disagree and ask for a
    sharper photo of that part of the slip ("the charges in the middle", "the total at the bottom"); buttons
    "New photo", "Type the units".
  - `difference` and `fits` come from the rules (capture/engine), never from the model.
- Unreadable or low confidence: name the field that could not be read ("I could not read the units" / "the energy
  charge") and where it is on the slip; buttons "New photo", "Type the units".
- A meter photo gets meter wording, never "lay the bill flat"; a meter photo with no bill on file keeps the reading
  and asks for the bill once.
- A file that would not open (corrupt, locked PDF, HEIC that will not decode, too large, unsupported type) says that,
  with the size limit or the types that work, never "not a bill".
- Not an electricity bill: buttons "Send my bill", "Type the units", "Help".
- Provider failed for good: say the reading did not work this time, then offer "Try again", "Type the units".
- The typed-units example must parse: "214 units October 2025" (or the parser accepts a month without a year as the
  latest such month).
- Bills from outside TGSPDCL/TGNPDCL (`discom == "OTHER"`) are never priced: say we only check Telangana bills.
- A bill month with no tariff version in force: price it only with a clear note that the nearest tariff was used, or
  refuse, never silently.
- Loops: the USC and code prompts get a Cancel button and the photo alternative; text that is clearly a question
  leaves the prompt instead of burning a code attempt; attempts left are shown.
- `need_bill` is not used after the person has just sent something; lost uploads say "that file did not reach us,
  please send it again".
- The generic failure (`service.py ERROR_TEXT`) moves to the lang packs, carries a short reference (section 2) and a
  "Try again" button.
- WhatsApp promises are kept: a parked turn or a failed deferred read sends one final neutral message with the next
  step (photo or type units), never silence.
- The web chat trace never carries config or exception text to a consumer (key names, model names, raw errors).

## 2. API errors (backend)

- One envelope for every error: `{"detail": {"code": "...", "message": "...", "ref": "..."}}` plus any extra fields
  (for example `attempts_left`). `message` is safe to show as is, in the request's language where the route takes
  `language`; `code` is a stable snake_case key; `ref` is a short request id (also in the `X-Request-Id` header and
  the server log line) so support can find the log.
- A global handler turns any unhandled exception into a 500 with that envelope ("Something went wrong on our side.
  Reference {ref}") and logs the exception type and ref only, never bodies or personal data.
- Validation errors (422) become one readable sentence (no "Value error," prefix, no field paths).
- No `str(exc)` from Python errors reaches a client: map known domain errors to messages, everything else to the
  generic one.
- The public webhook never reveals configuration.
- Rate limits say what was limited ("Too many uploads. Please wait a minute.").

## 3. Frontend

- `ApiError` reads the envelope (`message`, `code`, `ref`, extras); nothing shows "Request failed (N)".
- Every error on screen goes through `describeError`, with the reference shown small ("Reference ABC123") and a
  Try again where retrying is safe. No raw `error.message` anywhere.
- The dashboard extract wait ends: a queued read that ends in retake or not a bill opens that outcome; a failed one
  says so and offers Upload again and Type the units.
- The retake view shows the specific reason (translated) and the field to retake, and offers Type the units.
- The USC code step shows attempts left.
- The assistant chat shows a translated failure line with Try again, never a raw JS error.
