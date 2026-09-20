from __future__ import annotations

import io
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _invoice(gross: str, output: Path) -> None:
    image = Image.new("RGB", (1400, 1000), "white")
    draw = ImageDraw.Draw(image)
    title = _font(58)
    body = _font(39)
    small = _font(27)
    draw.rectangle((70, 60, 1330, 940), outline=(32, 49, 70), width=5)
    draw.text((120, 112), "INVOICE", font=title, fill=(25, 45, 70))
    draw.text((120, 205), "Invoice number: INV-0042", font=body, fill=(30, 30, 30))
    draw.text((120, 275), "Supplier: Northbank Supplies Ltd", font=body, fill=(30, 30, 30))
    draw.text((120, 345), "Issue date: 2026-09-19", font=body, fill=(30, 30, 30))
    draw.line((120, 425, 1280, 425), fill=(120, 135, 150), width=3)
    draw.text((170, 495), "Description", font=body, fill=(30, 30, 30))
    draw.text((990, 495), "Amount", font=body, fill=(30, 30, 30))
    draw.text((170, 570), "Document processing services", font=body, fill=(30, 30, 30))
    draw.text((170, 660), "Net: GBP 8,000.00", font=body, fill=(30, 30, 30))
    draw.text((170, 730), "VAT: GBP 1,600.00", font=body, fill=(30, 30, 30))
    draw.text((170, 800), f"Gross: GBP {gross}", font=body, fill=(25, 45, 70))
    draw.text(
        (120, 885),
        "Synthetic fixture — no personal or customer data",
        font=small,
        fill=(100, 110, 120),
    )

    # A small rotation and downsample create a realistic scanned-document boundary while
    # retaining enough signal for the deployed Tesseract proof.
    image = image.rotate(1.25, expand=True, fillcolor="white", resample=Image.Resampling.BICUBIC)
    image.thumbnail((1100, 800), Image.Resampling.LANCZOS)
    png = io.BytesIO()
    image.save(png, format="PNG", optimize=True)

    pdf = fitz.open()
    page = pdf.new_page(width=612, height=445)
    page.insert_image(page.rect, stream=png.getvalue())
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(output)
    pdf.close()


def main() -> None:
    _invoice("9,600.00", FIXTURES / "invoice_inv_0042_scan.pdf")
    _invoice("9,900.00", FIXTURES / "invoice_inv_0042_inconsistent_scan.pdf")


if __name__ == "__main__":
    main()
