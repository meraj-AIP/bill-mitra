"""Chart images for chat. WhatsApp cannot render charts, so the chart travels as a picture."""

import io

from PIL import Image, ImageDraw, ImageFont

from app.domain.prediction import MonthUsage

W, H = 1080, 640
INK, MUTED, GRID = (27, 42, 74), (107, 114, 128), (217, 222, 230)
BAR, CURRENT, LINE = (183, 196, 214), (18, 168, 83), (199, 120, 0)
BG = (255, 255, 255)
MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "Arial.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _dashed(draw: ImageDraw.ImageDraw, y: int, x0: int, x1: int) -> None:
    for x in range(x0, x1, 18):
        draw.line([(x, y), (min(x + 10, x1), y)], fill=LINE, width=3)


def trend_png(history: list[MonthUsage], current_month: str, current_units: int) -> bytes:
    months = [h for h in history if h.month != current_month][-11:]
    months.append(MonthUsage(month=current_month, units=current_units, amount=0))
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    left, right, top, bottom = 90, W - 40, 80, H - 90
    draw.text((left, 24), "Units per month", fill=INK, font=_font(30))
    top_units = max(260, max(m.units for m in months) + 30)
    scale = (bottom - top) / top_units
    for tick in range(0, top_units + 1, 50):
        y = bottom - int(tick * scale)
        draw.line([(left, y), (right, y)], fill=GRID, width=1)
        draw.text((20, y - 12), str(tick), fill=MUTED, font=_font(22))
    slot = (right - left) / len(months)
    for i, m in enumerate(months):
        x0 = left + int(i * slot + slot * 0.18)
        x1 = left + int((i + 1) * slot - slot * 0.18)
        is_current = i == len(months) - 1
        draw.rectangle([(x0, bottom - int(m.units * scale)), (x1, bottom)], fill=CURRENT if is_current else BAR)
        label = MONTH_SHORT[int(m.month[5:]) - 1]
        draw.text((x0, bottom + 12), label, fill=INK if is_current else MUTED, font=_font(22))
        if is_current:
            draw.text((x0 - 4, bottom - int(m.units * scale) - 34), str(m.units), fill=INK, font=_font(26))
    _dashed(draw, bottom - int(200 * scale), left, right)
    draw.text((right - 120, bottom - int(200 * scale) - 32), "200 units", fill=LINE, font=_font(22))
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
