from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "architecture.png"
W, H = 1400, 620
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("arial.ttf", 20)
    small = ImageFont.truetype("arial.ttf", 16)
except OSError:
    font = small = ImageFont.load_default(18)


def box(x, y, w, h, title, lines=(), fill=(232, 240, 252)):
    d.rounded_rectangle((x, y, x + w, y + h), radius=10, fill=fill, outline=(40, 60, 100), width=2)
    d.text((x + 14, y + 10), title, font=font, fill=(10, 20, 50))
    for i, line in enumerate(lines):
        d.text((x + 14, y + 42 + i * 22), line, font=small, fill=(50, 60, 80))


def arrow(x0, y0, x1, y1):
    d.line((x0, y0, x1, y1), fill=(40, 60, 100), width=3)
    d.polygon([(x1, y1), (x1 - 12, y1 - 7), (x1 - 12, y1 + 7)] if x1 > x0 else
              [(x1, y1), (x1 - 7, y1 + 12), (x1 + 7, y1 + 12)], fill=(40, 60, 100))


box(30, 250, 200, 110, "Telegram bot", ["document upload", "approve / reject"])
box(300, 40, 700, 540, "n8n on 1GB VPS (Docker + Caddy)", fill=(245, 247, 250))
steps = [
    ("01 Intake", "type and size checks"),
    ("02 Preprocess", "resize, PDF page count"),
    ("03 Classify", "invoice / ktp / spk"),
    ("04 Extract", "typed prompt + schema"),
    ("05 Validate", "schema + business rules"),
    ("06 Route and notify", "valid / review / failed"),
]
for i, (title, sub) in enumerate(steps):
    box(330, 85 + i * 80, 300, 66, title, [sub])
box(700, 150, 270, 90, "Fallback + retry", ["primary x2, then fallback"], fill=(252, 244, 228))
box(700, 330, 270, 90, "07 Error handler", ["admin alert + log"], fill=(252, 232, 232))
box(700, 450, 270, 90, "08 Weekly report", ["volume, cost, flagged"], fill=(238, 248, 238))
box(1090, 90, 280, 120, "Vision LLM APIs", ["Claude primary", "GPT / Gemini fallback"], fill=(240, 232, 252))
box(1090, 300, 280, 140, "Google Sheets", ["documents", "extractions", "run_logs"], fill=(232, 248, 238))
arrow(230, 305, 300, 305)
arrow(1000, 140, 1090, 140)
arrow(1000, 370, 1090, 370)
img.save(OUT)
print(f"wrote {OUT}")
