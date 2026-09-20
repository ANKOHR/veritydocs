from __future__ import annotations

import io
import shutil
from typing import Any

from PIL import Image

from .types import NormalizedPage, TextBlock


class OCRUnavailable(RuntimeError):
    pass


class TesseractOCREngine:
    """Real OCR adapter. The Docker image installs Tesseract; local runs fail closed if absent."""

    name = "tesseract"

    def __init__(self) -> None:
        if not shutil.which("tesseract"):
            raise OCRUnavailable("Tesseract OCR is not installed on this host")
        import pytesseract

        self._pytesseract = pytesseract

    def image_to_blocks(self, data: bytes) -> tuple[list[TextBlock], float]:
        image = Image.open(io.BytesIO(data))
        from pytesseract import Output

        result: dict[str, list[Any]] = self._pytesseract.image_to_data(
            image, output_type=Output.DICT
        )
        blocks: list[TextBlock] = []
        confidences: list[float] = []
        for index, raw_text in enumerate(result.get("text", [])):
            text = str(raw_text).strip()
            if not text:
                continue
            raw_conf = float(result["conf"][index])
            confidence = max(0.0, min(1.0, raw_conf / 100.0))
            confidences.append(confidence)
            blocks.append(
                TextBlock(
                    text=text,
                    bbox=[
                        result["left"][index],
                        result["top"][index],
                        result["left"][index] + result["width"][index],
                        result["top"][index] + result["height"][index],
                    ],
                    confidence=confidence,
                )
            )
        return blocks, sum(confidences) / len(confidences) if confidences else 0.0


def enrich_page_with_ocr(
    page: NormalizedPage, image_bytes: bytes, engine: TesseractOCREngine
) -> NormalizedPage:
    blocks, confidence = engine.image_to_blocks(image_bytes)
    page.blocks = blocks
    page.ocr_used = True
    page.ocr_confidence = confidence
    return page
