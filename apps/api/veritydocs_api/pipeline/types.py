from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextBlock:
    text: str
    bbox: list[float] | None = None
    kind: str = "text"
    confidence: float = 1.0
    section: str | None = None


@dataclass
class TableBlock:
    headers: list[str]
    rows: list[list[Any]]
    source_range: str | None = None
    confidence: float = 1.0


@dataclass
class NormalizedPage:
    page_number: int
    width: float | None = None
    height: float | None = None
    blocks: list[TextBlock] = field(default_factory=list)
    tables: list[TableBlock] = field(default_factory=list)
    image_key: str | None = None
    ocr_used: bool = False
    ocr_confidence: float = 1.0

    @property
    def text(self) -> str:
        if any(block.kind == "ocr_token" for block in self.blocks):
            chunks = [block.text for block in self.blocks if block.text]
            text = " ".join(chunks)
        else:
            text = "\n".join(block.text for block in self.blocks if block.text)
        for table in self.tables:
            text += ("\n" if text else "") + "\n".join(
                " | ".join(str(cell) for cell in row) for row in table.rows
            )
        return text


@dataclass
class NormalizedDocument:
    document_id: str
    filename: str
    mime_type: str
    pages: list[NormalizedPage]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)

    @property
    def average_ocr_confidence(self) -> float:
        if not self.pages:
            return 0.0
        return sum(page.ocr_confidence for page in self.pages) / len(self.pages)

    def find_evidence(self, needle: str) -> dict[str, Any] | None:
        normalized = needle.lower().strip()
        if not normalized:
            return None
        for page in self.pages:
            for block in page.blocks:
                if normalized in block.text.lower():
                    return {
                        "page": page.page_number,
                        "text": block.text.strip(),
                        "bbox": block.bbox,
                        "section": block.section,
                        "artifact_key": page.image_key,
                    }
            for table in page.tables:
                for row in table.rows:
                    text = " | ".join(str(cell) for cell in row)
                    if normalized in text.lower():
                        return {
                            "page": page.page_number,
                            "text": text,
                            "bbox": None,
                            "section": table.source_range,
                            "artifact_key": page.image_key,
                        }
        return None
