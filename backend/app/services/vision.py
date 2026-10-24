"""Read a bill or meter photo in two passes: a cheap look to decide what it is, then a careful read.

The first pass stops a selfie or a shop receipt from ever being "read" as a bill. Personal details
(name, address, phone) are deliberately not extracted.
"""

import asyncio
import base64
import contextlib
import io
import logging
from dataclasses import dataclass, replace
from math import ceil
from typing import Any, Literal

import pypdfium2 as pdfium
from PIL import Image, ImageFilter, ImageOps
from pillow_heif import register_heif_opener
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.core import retry
from app.domain import bill_normalise, capture, second_read
from app.domain.bill import ExtractedBill, PrintedLine
from app.services.openai_client import ProviderError, chat_json

log = logging.getLogger(__name__)
MAX_SIDE = 4096
TALL = 2.0  # height to width ratio above which a page is read in crops
MAX_CROPS = 4
MAX_PDF_PAGES = 3  # a bill plus its terms page; anything longer is not a single bill
# A phone photo is under 50 MP; a larger "image" is a decompression bomb, not a bill.
Image.MAX_IMAGE_PIXELS = 60_000_000
register_heif_opener()  # iPhone photos arrive as HEIC
# Per call (classify, read, reread). A read still failing after this is queued as an extract job by the caller.
READ = retry.Policy(attempts=3, base_s=2.0, max_s=20.0, budget_s=60.0)

DocumentKind = Literal["electricity_bill", "meter", "other_bill", "other"]

CLASSIFY = """You look at one photo or scanned page and decide what it is, before anyone reads it.
Return one JSON object with exactly these keys:
document_type: "electricity_bill" | "meter" | "other_bill" | "other"
  electricity_bill = an electricity bill or spot billing slip from any DISCOM, including the small thermal printed
  slips TGSPDCL and TGNPDCL meter readers hand out, a printed or PDF bill, or a screenshot of one.
  meter = a photo of an electricity meter display.
  other_bill = a bill or receipt that is not for electricity (water, gas, phone, shop, hospital).
  other = anything else.
discom: "TGSPDCL" | "TGNPDCL" | "OTHER" | "UNKNOWN"
quality: "good" | "poor" | "unreadable"
  good = text is sharp enough to read every number. poor = some of it is blurred, cut off, folded, in shadow or has
  glare. unreadable = the numbers cannot be read at all.
quality_issue: one short plain English sentence about what is wrong with the photo, or null if quality is good
reason: one short plain English sentence describing what you see, without any personal details"""

EXTRACT = """You read Indian electricity bills from Telangana DISCOMs (TGSPDCL, formerly TSSPDCL, and TGNPDCL) and
electricity meter photos. Most bills are narrow thermal spot billing slips ("Electricity Bill cum Notice")
photographed by hand: expect blur, tilt, curl, creases, shadows, glare and faded print. A tall slip may arrive as
several overlapping crops of the same page, top to bottom; read them together as one bill.
On these slips the value is often printed a little below or to the right of its label; match each value to its
label by position and by the totals, not by line alone.

Return one JSON object with exactly these keys:
document_type: "bill" | "meter" | "other"
is_electricity_bill: boolean
quality: "good" | "poor" | "unreadable"   (poor = any field below is blurred, cut off, folded or under glare)
quality_issue: one short plain English sentence, or null
meter_reading: number or null (only for a meter photo: the kWh register)
discom: "TGSPDCL" | "TGNPDCL" | "OTHER" | "UNKNOWN"   (TSSPDCL is the old name of TGSPDCL)
service_number: the USC No. exactly as printed (not the SC No. and not the meter number), or null
section: the "Sec:" value as printed, or null
category: as printed after "Cat", e.g. "1B(i) DOMESTIC", or null
is_domestic: true for category 1 / LT-I domestic, false for category 2 NON-DOMESTIC/COMMERCIAL, industrial, agriculture
bill_month: "YYYY-MM" of the bill date ("Dt:"), or null
bill_date: "YYYY-MM-DD" from "Dt:", or null
due_date: "YYYY-MM-DD" from "Due Date" (not "Disc Date", not "Last Paid"), or null
previous_reading_date: "YYYY-MM-DD" from the "Previous" reading row (dates are DD/MM/YY), or null
billing_days: the "Days:" number, or null
previous_reading, present_reading: readings from the "Previous" and "Present" rows, or null. Commercial and solar
  slips print them as "Prs DD/MM/YY Sts KWH KVAH" and "Prv DD/MM/YY Sts KWH KVAH": the two numbers after the date
  and the 2 digit status are the KWH and KVAH readings. Take the column the units are billed on, the one whose
  difference equals the units or the "Import:" value (these bills are usually billed on KVAH)
present_status, previous_status: the 2 digit status ("Sts") printed right after the date on the "Present"/"Prs" and
  "Previous"/"Prv" rows, e.g. "01", exactly as printed; null if there is none
units: the number printed after "Units:" (or "Billed Units:"), exactly as printed, or null. On a solar net-metered bill
  this is the billed (net) figure and is often 0; copy it as printed, do not replace it with the Import value
import_units: on a solar net-metered bill, the number printed after "Import:" (units drawn from the grid), else null
export_units: on a solar net-metered bill the "Export:" value (units sent to the grid), else null
export_previous_reading, export_present_reading: on a solar net-metered bill, the previous and present readings of
  the export register (rows marked "Exp", "Export" or "Exp KWH"), else null. TGSPDCL slips print them on one line as
  "Export Read : <previous> <present>". Keep them apart from the import readings above
billed_units: null (worked out from "Units:" and "Import:" after reading)
load_kw: "Contracted Load" in kW, or null
phase: 1 or 3 from "Ph:", or null
multiplying_factor: the "MF:" value, or null
recorded_md: the "Recorded MD" value, or null
power_factor: the "PF" value (0 to 1), or null
security_deposit: the "SD AVAILABLE" or "SD Available" amount, or null
carry_forward_units: the present "CF Units" or banked units value (from "Prev/Pres CF Units : a/b" take b), or null.
  On a solar bill that exported more than it imported, the extra is carried forward here and billed units are 0
previous_carry_forward_units: from "Prev/Pres CF Units : a/b" take a (units banked from earlier months), or null
disconnection_date: "YYYY-MM-DD" from "Disc Date", or null
last_paid_date: "YYYY-MM-DD" from "Last Paid Dt", or null
line_items: every charge row between the readings and "Bill Amount", as {code, label, amount}, label as printed,
  amounts negative when printed with a minus. Include rows that are 0.00. code is one of:
  energy = Energy Charges; fixed = Fixed Charges; customer = Customer Charges; duty = Electricity Duty only;
  fsa = FSA/FCA Charges; true_up = True-up; surcharge = Surcharge, ACD Surcharge, DPS;
  adjustment = Adjustment, Loss/Gain, rounding; other = Interest on ED, Interest on CD or SD, Subsidy row, anything else
bill_amount: the "Bill Amount" value, or null
arrears: the sum of the arrears rows ("Arrears", "Arrears as on ...", "Arrears after ...") plus "ACD Due", 0 if all are
  0.00. A row printed with a minus is a credit and makes the sum negative. Read each arrears row itself; never copy
  the Total Due figure into arrears
total_payable: the "Total Due" value, or null
gruha_jyothi_household: true if the bill mentions Gruha Jyothi or a 200 unit free scheme for this connection,
  false if it clearly does not, null if you cannot tell
subsidy_amount: Gruha Jyothi or other subsidy amount shown (0.00 counts as 0), or null
usage_history: list of {month: "YYYY-MM", units} from any past consumption table printed on the bill, oldest first;
  [] if there is none
unreadable_fields: names of the keys above that ARE printed on the bill but you cannot read with certainty
confidence: 0 to 1, your confidence that units and every amount are read correctly
Rules:
- Give every number as a plain JSON number: no commas, no "Rs", no units. An amount printed with "CR", a minus sign
  or in brackets is a credit: give it as a negative number. Dates as YYYY-MM-DD.
- When the bill prints a multiplying factor (MF) other than 1, the units are the reading difference times MF; still
  read the units as printed, never multiply yourself.
- Read numbers exactly as printed. Never calculate a value that is not printed (do not work out units from the
  readings, or a total from the charges). If it is not printed, use null.
- Thermal print confuses 0/8, 1/7, 3/8, 5/6. If a digit is ambiguous, put that key in unreadable_fields and lower
  confidence instead of guessing.
- Never include the consumer's name, address, phone numbers or the meter number."""


class Classification(BaseModel):
    document_type: DocumentKind
    discom: Literal["TGSPDCL", "TGNPDCL", "OTHER", "UNKNOWN"] = "UNKNOWN"
    quality: Literal["good", "poor", "unreadable"] = "good"
    quality_issue: str | None = None
    reason: str = ""


@dataclass
class Reading:
    classification: Classification
    bill: ExtractedBill | None  # None when the first pass stopped it
    reread: str | None = None  # why a second careful read was made: the failed check, or the figures it was unsure of
    reconciled: bool = False  # the two reads were settled together by the checks
    # Why nothing was read, when it was the file and not the photo: it would not open, or the bill was not in the
    # pages read.
    problem: Literal["unopenable", "too_long"] | None = None


MIN_SHORT_SIDE = 1000
# Deskew: angles tried, in degrees, and how much straighter the best one must score before the photo is turned.
SKEW_ANGLES = [a / 2 for a in range(-30, 31)]
SKEW_GAIN = 1.15
SKEW_MIN = 3.0  # degrees; a slighter tilt reads fine, and turning the image softens every digit a little
SKEW_PROBE = 400  # px, the short side of the small copy the angle is measured on


def _row_contrast(image: Image.Image) -> float:
    """How sharply the text lines stand apart: the summed change from one row's average darkness to the next.
    Straight print gives crisp edges between ink rows and white gaps; tilted print blurs every edge."""
    rows = list(image.resize((1, image.height), Image.Resampling.BOX).get_flattened_data())
    return sum((b - a) ** 2 for a, b in zip(rows, rows[1:], strict=False))


def skew_angle(image: Image.Image) -> float:
    """The rotation that makes the printed lines horizontal, or 0 when no angle is clearly better than none. Measured
    on the middle of the page, so a table or hand around the bill counts for little."""
    probe = ImageOps.grayscale(image)
    scale = SKEW_PROBE / min(probe.size)
    if scale < 1:
        probe = probe.resize((round(probe.width * scale), round(probe.height * scale)), Image.Resampling.BILINEAR)
    w, h = probe.size
    probe = ImageOps.autocontrast(probe.crop((w // 6, h // 6, w - w // 6, h - h // 6)), cutoff=2)
    probe = probe.point(lambda v: 0 if v < 140 else 255)
    scores = {a: _row_contrast(probe.rotate(a, resample=Image.Resampling.BILINEAR, fillcolor=255)) for a in SKEW_ANGLES}
    best = max(scores, key=lambda a: scores[a])
    return best if scores[0.0] == 0 or scores[best] >= scores[0.0] * SKEW_GAIN else 0.0


def deskewed(image: Image.Image) -> Image.Image:
    angle = skew_angle(image)
    if abs(angle) < SKEW_MIN:
        return image
    return image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(255, 255, 255))


# Paper: bright and nearly colourless. A slip on a patterned cloth or a table stands out from it.
PAPER_SAT, PAPER_VALUE = 45, 160
PAPER_PROBE = 400  # px, the long side of the small copy the paper is found on
PAPER_SHARE = 0.5  # of a column or row that must be paper for it to count
PAPER_MAX_AREA = 0.8  # a crop that would keep more than this of the photo is not worth making


def _longest_run(flags: list[bool], gap: int = 2) -> tuple[int, int] | None:
    """The longest stretch of True, bridging gaps of up to `gap` (a dark line of print across the paper)."""
    best, start, last = None, None, None
    for i, on in enumerate(flags + [False] * (gap + 1)):
        if on:
            start = i if start is None else start
            last = i
        elif start is not None and last is not None and i - last > gap:
            if best is None or last - start > best[1] - best[0]:
                best = (start, last)
            start = None
    return best


def paper_box(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Where the bill is, when it fills only part of the photo. A thermal slip photographed on a bed or a table is
    often a third of the frame's width; the reader then gets it at a fraction of the pixels and misreads digits.
    None when the paper already fills most of the photo, or no clear paper shape is found."""
    small = image.convert("RGB")
    scale = PAPER_PROBE / max(small.size)
    small = small.resize((max(round(small.width * scale), 1), max(round(small.height * scale), 1)), Image.Resampling.BOX)
    w, h = small.size
    hsv = list(small.convert("HSV").get_flattened_data())
    paper = [s <= PAPER_SAT and v >= PAPER_VALUE for _, s, v in hsv]
    cols = _longest_run([sum(paper[y * w + x] for y in range(h)) >= PAPER_SHARE * h * 0.6 for x in range(w)])
    if cols is None:
        return None
    x0, x1 = cols
    # A stamp, a fold or a pen mark over the name crosses the slip; a tenth of its height still counts as one paper.
    rows = _longest_run([sum(paper[y * w + x] for x in range(x0, x1 + 1)) >= PAPER_SHARE * (x1 - x0 + 1) for y in range(h)],
                        gap=max(2, h // 10))
    if rows is None:
        return None
    y0, y1 = rows
    if (x1 - x0) < w * 0.12 or (y1 - y0) < h * 0.3 or (x1 - x0) * (y1 - y0) > PAPER_MAX_AREA * w * h:
        return None
    pad_x, pad_y = round((x1 - x0) * 0.04) + 2, round((y1 - y0) * 0.02) + 2
    box = (max(x0 - pad_x, 0), max(y0 - pad_y, 0), min(x1 + pad_x + 1, w), min(y1 + pad_y + 1, h))
    return tuple(round(v / scale) for v in box)  # type: ignore[return-value]


def _bounded(image: Image.Image) -> bytes:
    image = image.convert("RGB")
    box = paper_box(image)
    image = deskewed(image.crop(box) if box else image)
    # WhatsApp shrinks a long thermal slip to about 330 px wide; enlarging it gives the reader room for each digit.
    short = min(image.size)
    if short < MIN_SHORT_SIDE:
        scale = min(MIN_SHORT_SIDE / short, MAX_SIDE / max(image.size))
        if scale > 1:
            image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    return _jpeg(image)


def pages(data: bytes, mime: str) -> list[bytes]:
    """Normalise any accepted upload to bounded JPEGs, one per page (photos have one)."""
    if mime != "application/pdf":
        return [_bounded(ImageOps.exif_transpose(Image.open(io.BytesIO(data))))]
    pdf = pdfium.PdfDocument(data)
    out = []
    for index in range(min(len(pdf), MAX_PDF_PAGES)):
        page = pdf[index]
        # Scanned slips are narrow; render so the short side has enough pixels for thermal digits.
        scale = min(max(1400 / min(page.get_size()), 2.0), 8.0)
        out.append(_bounded(page.render(scale=scale).to_pil()))
    return out


def to_jpeg(data: bytes, mime: str) -> bytes:
    return pages(data, mime)[0]


def _jpeg(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    return out.getvalue()


def crops(jpeg: bytes) -> list[bytes]:
    """Split a tall slip into overlapping crops. The vision API shrinks any image to fit 2048 px and then to
    768 px on the short side, so a 1:4 slip arrives about 500 px wide and its digits blur together."""
    image = Image.open(io.BytesIO(jpeg))
    width, height = image.size
    if height <= width * TALL:
        return [jpeg]
    parts = min(ceil(height / (width * 1.6)), MAX_CROPS)
    step, overlap = height / parts, int(height * 0.04)
    return [_jpeg(image.crop((0, max(int(i * step) - overlap, 0), width, min(int((i + 1) * step) + overlap, height))))
            for i in range(parts)]


def _content(images: list[bytes], detail: str, prompt: str) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for jpeg in images:
        url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        content.append({"type": "image_url", "image_url": {"url": url, "detail": detail}})
    return content


def _clean(raw: dict[str, Any]) -> dict[str, Any]:
    """The model's answer in one form (app/domain/bill_normalise.py), so one bad cell does not lose the whole bill."""
    return bill_normalise.normalise(raw)


async def classify(jpeg: bytes) -> Classification:
    model = get_settings().openai_vision_model
    raw = await chat_json(model, CLASSIFY, _content([jpeg], "low", "What is this?"), temperature=0,
                          max_tokens=200, policy=READ)
    try:
        return Classification.model_validate(raw)
    except ValidationError as exc:
        log.warning("classification failed validation: %s", exc.error_count())
        raise ProviderError("invalid classification") from exc


TRANSCRIBE = (" This time, add one more key FIRST in the JSON: transcript, a list of every printed line from top to"
              " bottom exactly as it appears, each label together with the number on its own line or nearest to it."
              " Then fill the other keys from your transcript. Report only what is printed; if you cannot be certain"
              " of a value, list its key in unreadable_fields.")
RECHECK = (" A rules check on your previous reading of this bill failed: {check}. So at least one number was"
           " misread, often because a value was matched to the label of the row above or below it." + TRANSCRIBE)
DOUBT = (" In your previous reading of this bill you could not be certain of: {keys}. The image is sharpened this"
         " time. Read those values again digit by digit." + TRANSCRIBE)
SUSPECTS = " Look hardest at these rows: {rows}."
# The second read gets a sharpened copy: thermal print fades unevenly, and a WhatsApp photo loses edge contrast.
SHARPEN = ImageFilter.UnsharpMask(radius=2, percent=160, threshold=2)


def sharpened(jpeg: bytes) -> bytes:
    image = Image.open(io.BytesIO(jpeg)).convert("L")
    return _jpeg(ImageOps.autocontrast(image, cutoff=1).filter(SHARPEN).convert("RGB"))


async def extract(jpeg: bytes, seen: Classification, failed_check: str | None = None,
                  suspects: list[str] | None = None, doubts: list[str] | None = None,
                  sharp: bool = False) -> ExtractedBill:
    """One careful read. On a second read, `failed_check` names the check that failed and `suspects` the rows to look
    at, or `doubts` the figures the first read was unsure of. Never the expected numbers, so the model cannot bend a
    value to fit the sum."""
    model = get_settings().openai_vision_model
    second = bool(failed_check or doubts)
    parts = crops(sharpened(jpeg) if second or sharp else jpeg)
    hint = f"A first look says this is: {seen.document_type}, {seen.discom}."
    if len(parts) > 1:
        hint += f" The page is sent as {len(parts)} overlapping crops, top to bottom."
    if failed_check:
        hint += RECHECK.format(check=failed_check.lower())
    elif doubts:
        hint += DOUBT.format(keys=", ".join(doubts))
    if suspects:
        hint += SUSPECTS.format(rows=", ".join(suspects))
    raw = await chat_json(model, EXTRACT, _content(parts, "high", hint + " Read it."), temperature=0,
                          max_tokens=3000 if second else 1600, policy=READ)
    raw.pop("transcript", None)
    try:
        return bill_normalise.to_bill(raw)
    except ValidationError as exc:
        log.warning("extraction failed validation: %s", exc.error_count())
        raise ProviderError("invalid extraction") from exc
    except (TypeError, ValueError) as exc:  # a shape _clean did not expect: the same as an invalid answer
        log.warning("extraction had an unexpected shape: %s", type(exc).__name__)
        raise ProviderError("invalid extraction") from exc


UNOPENABLE = Classification(document_type="other", quality="unreadable",
                            reason="The file could not be opened as a photo or a PDF.")


async def _first_document(images: list[bytes]) -> tuple[bytes, Classification]:
    """On a multi-page PDF the bill is not always page one; take the first page that looks like one."""
    seen = await classify(images[0])
    for jpeg in images[1:]:
        if seen.document_type in ("electricity_bill", "meter"):
            break
        candidate = await classify(jpeg)
        if candidate.document_type in ("electricity_bill", "meter"):
            return jpeg, candidate
    return images[0], seen


async def _second_read(jpeg: bytes, seen: Classification, first: ExtractedBill, failed: str | None) -> Reading:
    """A first read that failed a check, or was unsure of a key figure, gets one targeted second read. The second
    stands alone if it passes; otherwise the two reads are reconciled; otherwise the better one is kept untrusted."""
    doubts = second_read.doubtful(first)
    second = await extract(jpeg, seen, failed, suspects=second_read.suspect_rows(first) if failed else None,
                           doubts=None if failed else doubts)
    why = failed or f"unsure of {', '.join(doubts)}"
    # After a failed check the second read may stand alone. After doubt it stands only where both reads agree, so a
    # figure that is cut off or blurred away is never supplied by the reread.
    stands = capture.failed_check(second) is None and not second_read.doubtful(second)
    if stands and (failed or second_read.agrees_on(first, second, doubts)):
        return Reading(seen, second.model_copy(update={"unreadable_fields": [
            f for f in second.unreadable_fields if f not in doubts]}) if not failed else second, reread=why)
    settled = second_read.reconcile(first, second)
    if settled is not None:
        return Reading(seen, settled, reread=why, reconciled=True)
    # Neither stands: keep the one with no failed check, so the consumer is told what we could and could not read.
    kept = second if failed and capture.failed_check(second) is None else first
    return Reading(seen, kept, reread=why)


def _page_count(data: bytes, mime: str) -> int:
    return len(pdfium.PdfDocument(data)) if mime == "application/pdf" else 1


async def read_document(data: bytes, mime: str) -> Reading:
    try:
        images = pages(data, mime)
        count = _page_count(data, mime)
    except (OSError, ValueError, pdfium.PdfiumError, Image.DecompressionBombError):
        return Reading(UNOPENABLE, None, problem="unopenable")
    if not images:
        return Reading(UNOPENABLE, None, problem="unopenable")
    jpeg, seen = await _first_document(images)
    if seen.document_type not in ("electricity_bill", "meter") and count > MAX_PDF_PAGES:
        return Reading(seen, None, problem="too_long")
    # A bill from outside Telangana is never read further: the TG tariff cannot price it.
    if seen.document_type not in ("electricity_bill", "meter") or seen.quality == "unreadable" or \
            seen.discom == "OTHER":
        return Reading(seen, None)
    if seen.document_type == "meter":
        return await _settled(jpeg, seen, await _read_twice(jpeg, seen))
    bill, printed = await asyncio.gather(_read_twice(jpeg, seen), transcribe(jpeg))
    return _with_lines(await _settled(jpeg, seen, bill), printed)


async def _settled(jpeg: bytes, seen: Classification, bill: ExtractedBill) -> Reading:
    if bill.document_type == "meter":
        return Reading(seen, bill)
    failed = capture.failed_check(bill)
    if failed is None and not second_read.doubtful(bill):
        if not capture.register_misreads(bill):
            return Reading(seen, bill)
        # The amounts agree but a meter reading does not: look again at the readings before showing them.
        return _registers_checked(await _second_read(jpeg, seen, bill, "Present minus previous reading equals units"))
    return _registers_checked(await _second_read(jpeg, seen, bill, failed))


def _with_lines(reading: Reading, printed: list[PrintedLine]) -> Reading:
    if reading.bill is None or not printed or reading.bill.document_type == "meter":
        return reading
    return replace(reading, bill=reading.bill.model_copy(update={"printed": printed}))


PRINTED = """You copy an Indian electricity bill (TGSPDCL / TGNPDCL) line by line.
Return JSON {"printed": [{"label": "...", "value": "..."}]}: every line printed on the bill, top to bottom, label and
value exactly as printed (for example {"label": "STR CODE", "value": "1510097001"}, {"label": "Recorded MD",
"value": "1.84 KW"}, {"label": "Disc Date", "value": "03-11-2026"}). A heading has an empty value.
Leave out the consumer's name, address, mobile number and email entirely: never copy those lines or any part of them.
Copy only what is printed; never work anything out."""


async def transcribe(jpeg: bytes) -> list[PrintedLine]:
    """Every printed line, for questions about anything on the bill. Made alongside the reads and never needed for
    trust: a failure only means fewer questions can be answered from the bill's own lines."""
    if not get_settings().read_printed_lines:
        return []
    try:
        raw = await chat_json(get_settings().openai_vision_model, PRINTED,
                              _content(crops(jpeg), "high", "Copy every line."), temperature=0, max_tokens=2500,
                              policy=READ)
        return [PrintedLine.model_validate(line) for line in bill_normalise.printed_lines(raw.get("printed"))]
    except (ProviderError, ValidationError, AttributeError):
        return []


async def _read_twice(jpeg: bytes, seen: Classification) -> ExtractedBill:
    """Two reads at once, of the photo and of a sharpened copy, so they rarely share a misread. Where they disagree on
    a key figure a third read, told only which figures to look at, decides by majority; a figure with no majority is
    marked unreadable, never guessed. One read failing at the provider leaves the other to stand alone, as before."""
    if not get_settings().read_twice:
        return await extract(jpeg, seen)
    results = await asyncio.gather(extract(jpeg, seen), extract(jpeg, seen, sharp=True), return_exceptions=True)
    reads = [r for r in results if isinstance(r, ExtractedBill)]
    failures = [r for r in results if isinstance(r, BaseException)]
    # Only a provider failure lets the other read stand alone; anything else is a fault and is raised.
    if not reads or any(not isinstance(f, ProviderError) for f in failures):
        raise failures[0]
    if len(reads) == 1 or reads[0].document_type == "meter":
        return reads[0]
    differ = second_read.disagreements(reads[0], reads[1])
    if not differ:
        return reads[0]
    log.info("the two reads disagree on %s; a third read decides", ", ".join(differ))
    # Two reads that disagree and no third: nothing has a majority, so the disputed figures are unclear.
    with contextlib.suppress(ProviderError):
        reads.append(await extract(jpeg, seen, doubts=[second_read.ROW_NAMES.get(k, k) for k in differ]))
    voted, undecided = second_read.vote(reads)
    return second_read.mark_undecided(voted, undecided)


def _registers_checked(reading: Reading) -> Reading:
    """A reading that still does not add up after the second look is dropped and marked unreadable, never shown."""
    bill = reading.bill
    wrong = capture.register_misreads(bill) if bill is not None else []
    if bill is None or not wrong:
        return reading
    cleared = bill.model_copy(update={**dict.fromkeys(wrong), "unreadable_fields": sorted({*bill.unreadable_fields, *wrong})})
    return replace(reading, bill=cleared)
