"""Bill reading under real phone conditions: the two real scans in tests/real_bills, degraded the ways photos fail
(blur, motion, tilt, glare, darkness, WhatsApp compression, a cut-off bottom), read live and scored.

    python -m app.tools.eval_bills <out_dir> [--only mar24/tilt_on_table,...]

Makes live calls to the vision model (about two per case). The one outcome that must stay at zero is
TRUSTED_BUT_WRONG: a reading the checks accept whose numbers are not what is printed. "retake" means the consumer is
asked for a clearer photo, which is safe but costs them a step.
"""

import asyncio
import io
import json
import sys
import time
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from app.domain import capture
from app.services import vision

TRUTH = {  # read by hand from the clean scans
    "mar24": {"units": 157, "energy": 599.6, "customer": 90.0, "bill_amount": 774.0, "total_payable": 774.0},
    "oct25": {"units": 138, "energy": 518.2, "customer": 90.0, "bill_amount": 692.0, "total_payable": 1245.0},
}
FILES = {"mar24": "tests/real_bills/Adobe Scan 12 Mar 2024.pdf", "oct25": "tests/real_bills/Adobe Scan 5 Oct 2025.pdf"}


def base(path: str) -> Image.Image:
    page = pdfium.PdfDocument(path)[0]
    return page.render(scale=1100 / min(page.get_size())).to_pil().convert("RGB")


def jpeg(img: Image.Image, q: int = 85) -> bytes:
    out = io.BytesIO()
    img.save(out, "JPEG", quality=q)
    return out.getvalue()


def on_table(img: Image.Image, angle: float) -> Image.Image:
    return img.rotate(angle, expand=True, fillcolor=(96, 84, 70), resample=Image.BICUBIC)


def noise(img: Image.Image, amount: float) -> Image.Image:
    n = Image.effect_noise(img.size, 60).convert("RGB")
    return Image.blend(img, n, amount)


def glare(img: Image.Image) -> Image.Image:
    over = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(over)
    w, h = img.size
    d.ellipse((w * 0.25, h * 0.55, w * 1.05, h * 0.68), fill=235)
    over = over.filter(ImageFilter.GaussianBlur(w * 0.06))
    return Image.composite(Image.new("RGB", img.size, (255, 255, 250)), img, over)


def motion(img: Image.Image, k: int = 9) -> Image.Image:
    small = img.resize((img.width // 3, img.height // 3))
    blurred = small.filter(ImageFilter.Kernel((5, 5), [0] * 10 + [1] * 5 + [0] * 10, 5))
    for _ in range(k // 5):
        blurred = blurred.filter(ImageFilter.Kernel((5, 5), [0] * 10 + [1] * 5 + [0] * 10, 5))
    return blurred.resize(img.size)


VARIANTS = {
    "clean_photo": lambda i: jpeg(i, 88),
    "blur_mild": lambda i: jpeg(i.filter(ImageFilter.GaussianBlur(2.0))),
    "blur_heavy": lambda i: jpeg(i.filter(ImageFilter.GaussianBlur(5.0))),
    "blur_extreme": lambda i: jpeg(i.filter(ImageFilter.GaussianBlur(9.0))),
    "motion": lambda i: jpeg(motion(i)),
    "tilt_on_table": lambda i: jpeg(on_table(i, 9)),
    "dark_noisy": lambda i: jpeg(noise(ImageEnhance.Brightness(i).enhance(0.45), 0.25), 70),
    "glare_on_charges": lambda i: jpeg(glare(i)),
    "lowres_whatsapp": lambda i: jpeg(i.resize((i.width * 30 // 100, i.height * 30 // 100)), 35),
    "cut_bottom": lambda i: jpeg(i.crop((0, 0, i.width, int(i.height * 0.62)))),
    "everything": lambda i: jpeg(noise(ImageEnhance.Brightness(on_table(i.filter(ImageFilter.GaussianBlur(2.5)), -6))
                                       .enhance(0.6), 0.15).resize((i.width * 55 // 100, i.height * 55 // 100)), 45),
}


def score(name: str, truth: dict, r) -> dict:
    row = {"case": name, "class": r.classification.document_type, "quality": r.classification.quality, "reread": r.reread}
    if r.bill is None:
        return {**row, "outcome": "stopped_at_look", "why": r.classification.quality_issue or r.classification.reason}
    rep = capture.report(r.bill)
    got = {"units": r.bill.units, "energy": r.bill.item("energy"), "customer": r.bill.item("customer"),
           "bill_amount": r.bill.bill_amount, "total_payable": r.bill.total_payable}
    wrong = {k: (v, truth[k]) for k, v in got.items() if truth and v is not None and abs(v - truth[k]) > 0.01}
    missing = [k for k, v in got.items() if v is None]
    outcome = ("TRUSTED_BUT_WRONG" if wrong else "correct") if rep.trusted else "retake"
    return {**row, "outcome": outcome, "conf": r.bill.confidence, "captured": f"{rep.captured}/{rep.expected}",
            "wrong": wrong, "missing": missing, "why": rep.problem,
            "checks": {c.key: c.status for c in rep.checks}, "unreadable": r.bill.unreadable_fields}


async def run(sem, name, data, truth, mime="image/jpeg"):
    async with sem:
        t = time.monotonic()
        try:
            r = await vision.read_document(data, mime)
            row = score(name, truth, r)
        except Exception as exc:  # noqa: BLE001 - a provider failure is a result here, not a crash
            row = {"case": name, "outcome": "error", "why": f"{type(exc).__name__}: {exc}"}
        row["secs"] = round(time.monotonic() - t, 1)
        print(json.dumps(row), flush=True)
        return row


async def main(out: Path, only: set[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(2)
    jobs = []
    for bill, path in FILES.items():
        img = base(path)
        for vname, fn in VARIANTS.items():
            if only and f"{bill}/{vname}" not in only:
                continue
            data = fn(img)
            (out / f"{bill}_{vname}.jpg").write_bytes(data)
            jobs.append(run(sem, f"{bill}/{vname}", data, TRUTH[bill]))
    for extra in ("../frontend/public/partners.png", "../frontend/public/architecture.png"):
        if only or not Path(extra).exists():
            continue
        img = Image.open(extra).convert("RGB")
        jobs.append(run(sem, f"not_bill/{Path(extra).stem}", jpeg(img), {}))
    rows = await asyncio.gather(*jobs)
    bad = [r for r in rows if r["outcome"] == "TRUSTED_BUT_WRONG"]
    print("SUMMARY", json.dumps({o: sum(r["outcome"] == o for r in rows) for o in
                                 sorted({r["outcome"] for r in rows})}), "trusted_but_wrong:", len(bad))

if __name__ == "__main__":
    args = sys.argv[1:]
    picked = set(args[args.index("--only") + 1].split(",")) if "--only" in args else set()
    asyncio.run(main(Path(args[0]), picked))
