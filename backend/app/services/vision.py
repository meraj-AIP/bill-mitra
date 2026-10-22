"""Read a bill or meter photo in two passes: a cheap look to decide what it is, then a careful read.

The first pass stops a selfie or a shop receipt from ever being "read" as a bill. Personal details
(name, address, phone) are deliberately not extracted.
"""

import base64
import io
import logging
from dataclasses import dataclass
from math import ceil
from typing import Any, Literal

import pypdfium2 as pdfium
from PIL import Image, ImageFilter, ImageOps
from pillow_heif import register_heif_opener
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.core import retry
from app.domain import bill_normalise, capture, second_read
from app.domain.bill import ExtractedBill
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
units: the "Units:" value; on a solar net-metered bill the "Import:" value instead (units drawn from the grid), or null
export_units: on a solar net-metered bill the "Export:" value (units sent to the grid), else null
export_previous_reading, export_present_reading: on a solar net-metered bill, the previous and present readings of
  the export register (rows marked "Exp", "Export" or "Exp KWH"), else null. Keep them apart from the import
  readings above
billed_units: the "Billed Units:" value when printed (import minus export on net-metered bills), or null
load_kw: "Contracted Load" in kW, or null
phase: 1 or 3 from "Ph:", or null
multiplying_factor: the "MF:" value, or null
recorded_md: the "Recorded MD" value, or null
power_factor: the "PF" value (0 to 1), or null
security_deposit: the "SD AVAILABLE" or "SD Available" amount, or null
carry_forward_units: the present "CF Units" or banked units value (from "Prev/Pres CF Units : a/b" take b), or null.
  On a solar bill that exported more than it imported, the extra is carried forward here and billed units are 0
disconnection_date: "YYYY-MM-DD" from "Disc Date", or null
last_paid_date: "YYYY-MM-DD" from "Last Paid Dt", or null
line_items: every charge row between the readings and "Bill Amount", as {code, label, amount}, label as printed,
  amounts negative when printed with a minus. Include rows that are 0.00. code is one of:
  energy = Energy Charges; fixed = Fixed Charges; customer = Customer Charges; duty = Electricity Duty only;
  fsa = FSA/FCA Charges; true_up = True-up; surcharge = Surcharge, ACD Surcharge, DPS;
  adjustment = Adjustment, Loss/Gain, rounding; other = Interest on ED, Interest on CD or SD, Subsidy row, anything else
bill_amount: the "Bill Amount" value, or null
arrears: the sum of the arrears rows ("Arrears", "Arrears as on ...", "Arrears after ...") plus "ACD Due", 0 if all are
  0.00. A row printed with a minus is a credit and makes the sum negative; check it against Total Due minus Bill Amount
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


def _bounded(image: Image.Image) -> bytes:
    image = deskewed(image.convert("RGB"))
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
                  suspects: list[str] | None = None, doubts: list[str] | None = None) -> ExtractedBill:
    """One careful read. On a second read, `failed_check` names the check that failed and `suspects` the rows to look
    at, or `doubts` the figures the first read was unsure of. Never the expected numbers, so the model cannot bend a
    value to fit the sum."""
    model = get_settings().openai_vision_model
    second = bool(failed_check or doubts)
    parts = crops(sharpened(jpeg) if second else jpeg)
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


async def read_document(data: bytes, mime: str) -> Reading:
    try:
        images = pages(data, mime)
    except (OSError, ValueError, pdfium.PdfiumError, Image.DecompressionBombError):
        return Reading(UNOPENABLE, None)
    if not images:
        return Reading(UNOPENABLE, None)
    jpeg, seen = await _first_document(images)
    if seen.document_type not in ("electricity_bill", "meter") or seen.quality == "unreadable":
        return Reading(seen, None)
    bill = await extract(jpeg, seen)
    if bill.document_type == "meter":
        return Reading(seen, bill)
    failed = capture.failed_check(bill)
    if failed is None and not second_read.doubtful(bill):
        return Reading(seen, bill)
    return await _second_read(jpeg, seen, bill, failed)
