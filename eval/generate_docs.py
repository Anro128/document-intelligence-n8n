import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CATALOG = json.loads((ROOT / "schemas" / "vehicle_catalog.json").read_text(encoding="utf-8"))

FONT_NAMES = ["arial.ttf", "times.ttf", "cour.ttf", "verdana.ttf", "calibri.ttf",
              "DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
FIRST = ["Budi", "Siti", "Agus", "Dewi", "Rizky", "Putri", "Andi", "Sari", "Hendra", "Maya",
         "Fajar", "Lestari", "Bayu", "Ratna", "Doni", "Wulan"]
LAST = ["Santoso", "Wijaya", "Pratama", "Hidayat", "Nugroho", "Saputra", "Kusuma", "Rahayu",
        "Setiawan", "Permata", "Firmansyah", "Utami"]
STREETS = ["JL. MELATI", "JL. MAWAR", "JL. KENANGA", "JL. MERDEKA", "JL. SUDIRMAN",
           "JL. PAHLAWAN", "JL. CEMPAKA", "JL. DIPONEGORO"]
VENDORS = ["PT Sumber Otomotif Jaya", "CV Mitra Sparepart", "PT Autoparts Nusantara",
           "Bengkel Resmi Maju Bersama", "PT Karoseri Prima", "CV Roda Mas"]
PARTS = ["Oli Mesin 4L", "Filter Udara", "Kampas Rem Depan", "Busi Iridium", "Aki 45Ah",
         "Ban 185/65 R15", "Wiper Blade", "Accu Cleaner", "Filter Oli", "Lampu LED H4",
         "Servis Berkala", "Spooring Balancing"]
COLORS = ["Putih", "Hitam", "Silver", "Abu-abu", "Merah", "Biru"]
AREAS = ["327101", "317404", "337401", "357801", "347101", "510101"]
PAYMENT_LABELS = {"cash": "Tunai", "credit": "Kredit", "leasing": "Leasing"}
DATE_FMTS = ["%d/%m/%Y", "%d-%m-%Y", "%d %b %Y"]


def usable_fonts():
    found = []
    for name in FONT_NAMES:
        try:
            ImageFont.truetype(name, 12)
            found.append(name)
        except OSError:
            continue
    return found or [None]


FONTS = usable_fonts()


class Page:
    def __init__(self, rng, width, height, bg):
        self.img = Image.new("RGB", (width, height), bg)
        self.draw = ImageDraw.Draw(self.img)
        self.font_name = rng.choice(FONTS)

    def font(self, size):
        if self.font_name is None:
            return ImageFont.load_default(size)
        return ImageFont.truetype(self.font_name, size)

    def text(self, xy, value, size=22, fill=(20, 20, 20)):
        self.draw.text(xy, value, font=self.font(size), fill=fill)

    def right(self, x, y, value, size=22):
        width = self.draw.textlength(value, font=self.font(size))
        self.text((x - width, y), value, size)

    def line(self, y, x0=50, x1=850):
        self.draw.line((x0, y, x1, y), fill=(0, 0, 0), width=2)


def rupiah(value):
    return f"{value:,}".replace(",", ".")


def distort(img, rng):
    angle = rng.uniform(-2.5, 2.5)
    img = img.rotate(angle, expand=True, fillcolor=(235, 235, 235), resample=Image.BICUBIC)
    if rng.random() < 0.5:
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.4, 1.2)))
    noise = Image.effect_noise(img.size, rng.uniform(6, 16)).convert("RGB")
    return ImageChops.add(img, noise, 1.0, -128)


def make_invoice(rng, inject):
    page = Page(rng, 900, 1000, (255, 255, 255))
    vendor = rng.choice(VENDORS)
    items = []
    for _ in range(rng.randint(2, 6)):
        qty = rng.randint(1, 4)
        unit = rng.randrange(50, 3000) * 1000
        items.append({"description": rng.choice(PARTS), "quantity": qty,
                      "unit_price": unit, "amount": qty * unit})
    subtotal = sum(i["amount"] for i in items)
    tax = round(subtotal * 0.11)
    total = subtotal + tax
    error = None
    if inject:
        total += rng.choice([-1, 1]) * rng.randrange(10, 500) * 1000
        error = "total_mismatch"
    when = date.today() - timedelta(days=rng.randint(5, 700))
    number = f"INV/{when.year}/{rng.randint(1, 9999):04d}"

    page.text((50 if rng.random() < 0.5 else 450, 40), vendor, 34)
    page.text((50, 110), "INVOICE", 28)
    page.text((50, 160), f"No: {number}", 22)
    page.text((50, 195), f"Tanggal: {when.strftime(rng.choice(DATE_FMTS))}", 22)
    y = 270
    page.line(y)
    page.text((60, y + 10), "Deskripsi", 20)
    page.right(580, y + 10, "Qty", 20)
    page.right(710, y + 10, "Harga", 20)
    page.right(840, y + 10, "Jumlah", 20)
    y += 50
    page.line(y)
    y += 15
    for item in items:
        page.text((60, y), item["description"], 20)
        page.right(580, y, str(item["quantity"]), 20)
        page.right(710, y, rupiah(item["unit_price"]), 20)
        page.right(840, y, rupiah(item["amount"]), 20)
        y += 40
    page.line(y + 5)
    y += 25
    for label, value in (("Subtotal", subtotal), ("PPN 11%", tax), ("Total", total)):
        page.text((560, y), label, 22)
        page.right(840, y, rupiah(value), 22)
        y += 38
    page.text((40, 965), "SYNTHETIC DEMO DOCUMENT", 14, (120, 120, 120))

    fields = {"invoice_number": number, "date": when.isoformat(), "vendor": vendor,
              "line_items": items, "subtotal": subtotal, "tax": tax, "total": total}
    return page.img, fields, error


def make_nik(rng, birth, gender):
    day = birth.day + (40 if gender == "female" else 0)
    serial = rng.randint(1, 9999)
    return f"{rng.choice(AREAS)}{day:02d}{birth.month:02d}{birth.year % 100:02d}{serial:04d}"


def make_ktp(rng, inject):
    bg = rng.choice([(205, 226, 245), (220, 235, 215), (245, 235, 210)])
    page = Page(rng, 1000, 640, bg)
    gender = rng.choice(["male", "female"])
    name = f"{rng.choice(FIRST)} {rng.choice(LAST)}".upper()
    birth = date(rng.randint(1960, 2004), rng.randint(1, 12), rng.randint(1, 28))
    nik = make_nik(rng, birth, gender)
    error = None
    if inject:
        error = rng.choice(["nik_birth_mismatch", "nik_length"])
        if error == "nik_length":
            nik = nik[:-1]
        else:
            nik = make_nik(rng, birth.replace(month=birth.month % 12 + 1), gender)
    street = f"{rng.choice(STREETS)} NO. {rng.randint(1, 150)}"
    place = rng.choice(["BANDUNG", "BOGOR", "SEMARANG", "SURABAYA", "DENPASAR"])

    page.text((300, 20), "PROVINSI JAWA BARAT", 30)
    page.text((340, 60), "KOTA BANDUNG", 26)
    page.text((40, 120), "NIK", 28)
    page.text((290, 120), f": {nik}", 34)
    rows = [
        ("Nama", name),
        ("Tempat/Tgl Lahir", f"{place}, {birth.strftime('%d-%m-%Y')}"),
        ("Jenis Kelamin", "LAKI-LAKI" if gender == "male" else "PEREMPUAN"),
        ("Alamat", street),
        ("RT/RW", f"{rng.randint(1, 9):03d}/{rng.randint(1, 9):03d}"),
        ("Kel/Desa", "SUKAMAJU"),
        ("Kecamatan", "CIBEUNYING"),
        ("Agama", "ISLAM"),
        ("Pekerjaan", "KARYAWAN SWASTA"),
    ]
    y = 180
    for label, value in rows:
        page.text((40, y), label, 24)
        page.text((290, y), f": {value}", 24)
        y += 40
    page.text((40, 610), "SYNTHETIC DEMO DOCUMENT", 14, (110, 110, 110))

    fields = {"nik": nik, "name": name, "birth_date": birth.isoformat(),
              "address": street, "gender": gender}
    return page.img, fields, error


def make_spk(rng, inject):
    page = Page(rng, 900, 800, (255, 255, 255))
    model = rng.choice(list(CATALOG))
    info = CATALOG[model]
    low, high = info["price"]
    price = rng.randrange(low, high, 5_000_000)
    error = None
    if inject:
        price = high + rng.randrange(150, 500) * 1_000_000
        error = "price_out_of_range"
    variant = rng.choice(info["variants"])
    color = rng.choice(COLORS)
    payment = rng.choice(list(PAYMENT_LABELS))
    customer = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    when = date.today() - timedelta(days=rng.randint(1, 365))
    number = f"SPK/{when.year}/{when.month:02d}/{rng.randint(1, 999):03d}"

    page.text((50, 40), "SURAT PESANAN KENDARAAN", 32)
    page.text((50, 100), "Dealer Resmi Demo Motor", 22)
    page.line(150)
    rows = [
        ("No. SPK", number),
        ("Tanggal", when.strftime(rng.choice(DATE_FMTS))),
        ("Nama Pemesan", customer),
        ("Model", model),
        ("Varian", variant),
        ("Warna", color),
        ("Harga OTR", f"Rp {rupiah(price)}"),
        ("Cara Bayar", PAYMENT_LABELS[payment]),
    ]
    y = 190
    for label, value in rows:
        page.text((60, y), label, 24)
        page.text((340, y), f": {value}", 24)
        y += 55
    page.line(y + 10)
    page.text((60, y + 40), "Tanda tangan pemesan", 18)
    page.text((40, 765), "SYNTHETIC DEMO DOCUMENT", 14, (120, 120, 120))

    fields = {"spk_number": number, "customer_name": customer, "model": model,
              "variant": variant, "color": color, "price": price, "payment_method": payment}
    return page.img, fields, error


MAKERS = {"invoice": make_invoice, "ktp": make_ktp, "spk": make_spk}


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic documents and ground truth")
    parser.add_argument("--per-type", type=int, default=30)
    parser.add_argument("--error-rate", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    docs_dir = ROOT / "data" / "synthetic"
    truth_dir = ROOT / "data" / "ground_truth"
    docs_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)

    for doc_type, maker in MAKERS.items():
        for index in range(1, args.per_type + 1):
            doc_id = f"{doc_type}_{index:03d}"
            img, fields, error = maker(rng, rng.random() < args.error_rate)
            distort(img, rng).save(docs_dir / f"{doc_id}.jpg", quality=82)
            record = {"id": doc_id, "doc_type": doc_type, "injected_error": error, "fields": fields}
            (truth_dir / f"{doc_id}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"generated {args.per_type * len(MAKERS)} documents in {docs_dir}")


if __name__ == "__main__":
    main()
