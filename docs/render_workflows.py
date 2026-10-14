import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "workflows"
S = 2
NODE = 88
GAP_X, GAP_Y = 190, 175
PAD = 110

BG = (27, 25, 33)
DOT = (52, 50, 62)
CARD = (54, 52, 64)
CARD_LINE = (118, 116, 130)
WIRE = (150, 148, 162)
TEXT = (205, 203, 214)
SUB = (140, 138, 152)

TRIGGERS = {"webhook", "executeWorkflowTrigger", "errorTrigger", "scheduleTrigger"}
BRANCH_LABELS = {
    "Route update": ["file", "callback", "other"],
    "Route status": ["valid", "review", "failed"],
    "Is image": ["true", "false"],
    "Has extraction": ["true", "false"],
}


def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size * S)
        except OSError:
            continue
    return ImageFont.load_default(size * S)


def wrap(text, width=17):
    words, lines, line = text.split(), [], ""
    for word in words:
        if line and len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line]


def bolt(d, x, y, h, color=(255, 90, 80)):
    pts = [(0.55, 0), (0.1, 0.55), (0.45, 0.55), (0.3, 1), (0.9, 0.4), (0.5, 0.4)]
    d.polygon([(x + px * h * 0.55, y + py * h) for px, py in pts], fill=color)


def icon(d, kind, cx, cy):
    u = NODE * S / 100
    if kind == "code":
        d.text((cx, cy), "{ }", font=font(34), fill=(255, 150, 60), anchor="mm")
    elif kind in ("if", "switch"):
        color = (80, 190, 130) if kind == "if" else (80, 170, 240)
        d.line((cx - 24 * u, cy, cx - 4 * u, cy), fill=color, width=int(4 * u))
        d.line((cx - 4 * u, cy, cx + 10 * u, cy - 16 * u), fill=color, width=int(4 * u))
        d.line((cx - 4 * u, cy, cx + 10 * u, cy + 16 * u), fill=color, width=int(4 * u))
        d.line((cx + 10 * u, cy - 16 * u, cx + 24 * u, cy - 16 * u), fill=color, width=int(4 * u))
        d.line((cx + 10 * u, cy + 16 * u, cx + 24 * u, cy + 16 * u), fill=color, width=int(4 * u))
    elif kind == "googleSheets":
        box = (cx - 20 * u, cy - 25 * u, cx + 20 * u, cy + 25 * u)
        d.rounded_rectangle(box, radius=4 * u, fill=(35, 160, 90))
        for dy in (-8, 4, 16):
            d.line((cx - 13 * u, cy + dy * u, cx + 13 * u, cy + dy * u), fill="white", width=int(2.5 * u))
        d.line((cx, cy - 18 * u, cx, cy + 20 * u), fill="white", width=int(2.5 * u))
    elif kind == "executeWorkflow":
        d.rounded_rectangle((cx - 4 * u, cy - 20 * u, cx + 24 * u, cy + 20 * u), radius=5 * u, outline=(150, 120, 245), width=int(4 * u))
        d.line((cx - 26 * u, cy, cx + 8 * u, cy), fill=(150, 120, 245), width=int(4 * u))
        d.polygon([(cx + 14 * u, cy), (cx + 4 * u, cy - 9 * u), (cx + 4 * u, cy + 9 * u)], fill=(150, 120, 245))
    elif kind == "readWriteFile":
        d.polygon([(cx - 15 * u, cy - 24 * u), (cx + 6 * u, cy - 24 * u), (cx + 18 * u, cy - 12 * u),
                   (cx + 18 * u, cy + 24 * u), (cx - 15 * u, cy + 24 * u)], fill=(225, 225, 235))
        d.line((cx - 8 * u, cy, cx + 11 * u, cy), fill=(110, 110, 125), width=int(3 * u))
        d.line((cx - 8 * u, cy + 10 * u, cx + 11 * u, cy + 10 * u), fill=(110, 110, 125), width=int(3 * u))
    elif kind == "editImage":
        d.rounded_rectangle((cx - 24 * u, cy - 19 * u, cx + 24 * u, cy + 19 * u), radius=5 * u, outline=(90, 190, 240), width=int(4 * u))
        d.polygon([(cx - 16 * u, cy + 12 * u), (cx - 3 * u, cy - 6 * u), (cx + 6 * u, cy + 6 * u),
                   (cx + 12 * u, cy - 1 * u), (cx + 18 * u, cy + 12 * u)], fill=(90, 190, 240))
    elif kind == "webhook":
        c = (230, 110, 160)
        for px, py in ((-16, 14), (16, 14), (0, -18)):
            d.ellipse((cx + (px - 7) * u, cy + (py - 7) * u, cx + (px + 7) * u, cy + (py + 7) * u), outline=c, width=int(4 * u))
        d.line((cx - 16 * u, cy + 14 * u, cx, cy - 18 * u, cx + 16 * u, cy + 14 * u), fill=c, width=int(3 * u))
    elif kind == "executeWorkflowTrigger":
        icon(d, "executeWorkflow", cx, cy)
    elif kind == "errorTrigger":
        d.polygon([(cx, cy - 24 * u), (cx + 26 * u, cy + 20 * u), (cx - 26 * u, cy + 20 * u)], fill=(240, 90, 90))
        d.text((cx, cy + 6 * u), "!", font=font(28), fill="white", anchor="mm")
    elif kind == "scheduleTrigger":
        d.ellipse((cx - 24 * u, cy - 24 * u, cx + 24 * u, cy + 24 * u), outline=(90, 190, 240), width=int(4 * u))
        d.line((cx, cy, cx, cy - 15 * u), fill=(90, 190, 240), width=int(4 * u))
        d.line((cx, cy, cx + 12 * u, cy + 6 * u), fill=(90, 190, 240), width=int(4 * u))
    else:
        d.ellipse((cx - 10 * u, cy - 10 * u, cx + 10 * u, cy + 10 * u), fill=SUB)


def draw_node(d, node, x, y):
    kind = node["type"].split(".")[-1]
    w = NODE * S
    left, top = x * S, y * S
    if kind in TRIGGERS:
        d.rounded_rectangle((left, top, left + w, top + w), radius=w // 2 - 3 * S, fill=CARD, outline=CARD_LINE, width=2 * S)
        d.rounded_rectangle((left + w // 2 - S, top, left + w, top + w), radius=14 * S, fill=CARD, outline=CARD_LINE,
                            width=2 * S, corners=(False, True, True, False))
        d.rectangle((left + w // 2 - 2 * S, top + 3 * S, left + w // 2 + 2 * S, top + w - 3 * S), fill=CARD)
        bolt(d, left - 26 * S, top + w / 2 - 17 * S, 34 * S)
    else:
        d.rounded_rectangle((left, top, left + w, top + w), radius=14 * S, fill=CARD, outline=CARD_LINE, width=2 * S)
    icon(d, kind, left + w / 2, top + w / 2)
    for i, line in enumerate(wrap(node["name"])):
        d.text((left + w / 2, top + w + (14 + i * 19) * S), line, font=font(15), fill=TEXT, anchor="mm")


def port_y(node_y, index, count):
    mid = node_y + NODE / 2
    return mid + (index - (count - 1) / 2) * 26


def bezier(p0, p3):
    dx = max(45 * S, abs(p3[0] - p0[0]) * 0.5)
    p1, p2 = (p0[0] + dx, p0[1]), (p3[0] - dx, p3[1])
    pts = []
    for i in range(41):
        t = i / 40
        a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + e * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + e * p3[1]))
    return pts


def render(path):
    wf = json.loads(path.read_text(encoding="utf-8"))
    nodes = {n["name"]: n for n in wf["nodes"]}
    pos = {name: (PAD + n["position"][0] / 260 * GAP_X, PAD + n["position"][1] / 220 * GAP_Y) for name, n in nodes.items()}
    width = int(max(x for x, _ in pos.values()) + NODE + PAD)
    height = int(max(y for _, y in pos.values()) + NODE + PAD + 30)
    title_h = 60
    img = Image.new("RGB", (width * S, (height + title_h) * S), BG)
    d = ImageDraw.Draw(img)
    for gx in range(0, width, 22):
        for gy in range(0, height + title_h, 22):
            d.ellipse((gx * S - 1, gy * S - 1, gx * S + 1, gy * S + 1), fill=DOT)
    d.text((28 * S, 30 * S), wf["name"], font=font(22), fill=TEXT, anchor="lm")

    def out_count(name, linked):
        kind = nodes[name]["type"]
        return max(linked, 3 if kind.endswith("switch") else 0, 2 if kind.endswith(".if") else 0)

    def branch_labels(name, count):
        return BRANCH_LABELS.get(name, [str(i) for i in range(count)])

    shifted = {name: (x, y + title_h) for name, (x, y) in pos.items()}
    for src, conn in wf["connections"].items():
        outputs = conn["main"]
        sx, sy = shifted[src]
        for out_index, targets in enumerate(outputs):
            for target in targets:
                tx, ty = shifted[target["node"]]
                count = out_count(src, len(outputs))
                start = (sx + NODE) * S
                if count > 1:
                    start += d.textlength(branch_labels(src, count)[out_index], font=font(12)) + 18 * S
                p0 = (start, port_y(sy, out_index, count) * S)
                p3 = (tx * S, (ty + NODE / 2) * S)
                pts = bezier(p0, p3)
                d.line(pts, fill=WIRE, width=3 * S, joint="curve")
                d.polygon([(p3[0], p3[1]), (p3[0] - 10 * S, p3[1] - 6 * S), (p3[0] - 10 * S, p3[1] + 6 * S)], fill=WIRE)

    for name, node in nodes.items():
        x, y = shifted[name]
        draw_node(d, node, x, y)
        outputs = wf["connections"].get(name, {}).get("main", [])
        count = out_count(name, len(outputs))
        if count > 1:
            labels = branch_labels(name, count)
            for i in range(count):
                py = port_y(y, i, count) * S
                d.ellipse(((x + NODE) * S - 5 * S, py - 5 * S, (x + NODE) * S + 5 * S, py + 5 * S), fill=WIRE)
                d.text(((x + NODE) * S + 12 * S, py), labels[i], font=font(12), fill=SUB, anchor="lm")
        else:
            py = (y + NODE / 2) * S
            d.ellipse(((x + NODE) * S - 5 * S, py - 5 * S, (x + NODE) * S + 5 * S, py + 5 * S), fill=WIRE)

    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{path.stem}.png"
    img.resize((width, height + title_h), Image.LANCZOS).save(target)
    return target


def main():
    for path in sorted((ROOT / "workflows").glob("0*.json")):
        print("wrote", render(path).relative_to(ROOT))


if __name__ == "__main__":
    main()
