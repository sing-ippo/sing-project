from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import fitz  # PyMuPDF
from PIL import Image


class FormulaExtractionError(Exception):
    """Base error for formula extraction."""


class Pix2TextNotInstalledError(FormulaExtractionError):
    """Raised when pix2text is unavailable."""


FORMULA_KEYS = ("formula_id", "page", "latex", "context", "method", "confidence")
FORMULA_TYPES = {"embedding", "isolated"}


def _load_pix2text():
    try:
        from pix2text import Pix2Text  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on runtime env
        raise Pix2TextNotInstalledError(
            "pix2text is not installed. Install dependencies from requirements.txt"
        ) from exc
    return Pix2Text


def is_pix2text_available() -> bool:
    try:
        _load_pix2text()
        return True
    except Pix2TextNotInstalledError:
        return False


def pdf_page_to_pil(page: fitz.Page, zoom: float = 2.0) -> Image.Image:
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


def normalize_bbox(position: Any) -> Optional[Tuple[float, float, float, float]]:
    if position is None:
        return None
    if hasattr(position, "tolist"):
        position = position.tolist()
    try:
        if (
            isinstance(position, (list, tuple))
            and len(position) == 4
            and all(isinstance(v, (int, float)) for v in position)
        ):
            x0, y0, x1, y1 = position
            return float(min(x0, x1)), float(min(y0, y1)), float(max(x0, x1)), float(max(y0, y1))

        if isinstance(position, (list, tuple)) and len(position) >= 2:
            pts = []
            for point in position:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    pts.append((float(point[0]), float(point[1])))
            if pts:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None
    return None


def image_bbox_to_pdf_bbox(
    bbox_img: Optional[Tuple[float, float, float, float]], zoom: float
) -> Optional[Tuple[float, float, float, float]]:
    if bbox_img is None:
        return None
    x0, y0, x1, y1 = bbox_img
    return x0 / zoom, y0 / zoom, x1 / zoom, y1 / zoom


def clean_text(text: str) -> str:
    return " ".join((text or "").split())


def extract_context_from_pdf_words(
    page: fitz.Page,
    formula_bbox_pdf: Optional[Tuple[float, float, float, float]],
    context_words: int = 40,
    x_margin: float = 140.0,
    y_margin: float = 45.0,
) -> str:
    words = page.get_text("words")
    if not words:
        return ""

    words = sorted(words, key=lambda w: (w[5], w[6], w[7]))

    if formula_bbox_pdf is None:
        return clean_text(" ".join(w[4] for w in words[:context_words]))

    fx0, fy0, fx1, fy1 = formula_bbox_pdf
    fcx = (fx0 + fx1) / 2
    fcy = (fy0 + fy1) / 2

    scored: list[tuple[float, tuple]] = []
    for word in words:
        x0, y0, x1, y1, *_rest = word
        wcx = (x0 + x1) / 2
        wcy = (y0 + y1) / 2
        close_horiz = (x1 >= fx0 - x_margin) and (x0 <= fx1 + x_margin)
        close_vert = (y1 >= fy0 - y_margin) and (y0 <= fy1 + y_margin)
        dist = abs(wcy - fcy) * 3 + abs(wcx - fcx) * 0.15
        scored.append((0.0 if (close_horiz and close_vert) else dist, word))

    nearest = sorted(scored, key=lambda item: item[0])[:context_words]
    selected = sorted((w for _, w in nearest), key=lambda w: (w[5], w[6], w[7]))
    return clean_text(" ".join(w[4] for w in selected))


_LATEXISH_RE = re.compile(
    r"(\\[A-Za-z]+|\^|_|=|\\frac|\\sum|\\int|√|∑|∫|λ|μ|σ|Δ|∇|∞|[A-Za-z]\([^)]+\))"
)


def _clean_latex(text: str) -> str:
    return clean_text(text).strip("$ ")


# strict spec: formula_id, page, latex, context, method, confidence
# no extra fields are returned

def extract_formulas(
    pdf_path: str,
    pages: Optional[List[int]] = None,
    zoom: float = 2.0,
    resized_shape: int = 768,
    device: Optional[str] = None,
    mfr_batch_size: int = 1,
    context_words: int = 40,
) -> List[Dict[str, Any]]:
    """
    Extract formulas from PDF using Pix2Text.

    Returns a list of dicts with exactly these keys:
    formula_id, page, latex, context, method, confidence
    """
    Pix2Text = _load_pix2text()
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    try:
        if pages is None:
            pages_to_process = list(range(1, len(doc) + 1))
        else:
            pages_to_process = [p for p in pages if 1 <= p <= len(doc)]

        if not pages_to_process:
            return []

        p2t = Pix2Text.from_config(enable_table=False, device=device)
        results: list[dict[str, Any]] = []
        formula_counter = 1

        for page_num in pages_to_process:
            page = doc[page_num - 1]
            image = pdf_page_to_pil(page, zoom=zoom)
            blocks = p2t.recognize_text_formula(
                image,
                return_text=False,
                resized_shape=resized_shape,
                mfr_batch_size=mfr_batch_size,
            )

            normalized_blocks = []
            for block in blocks:
                position = normalize_bbox(block.get("position"))
                normalized_blocks.append((position, block))

            normalized_blocks.sort(
                key=lambda item: (
                    item[0][1] if item[0] else 10**9,
                    item[0][0] if item[0] else 10**9,
                )
            )

            for bbox_img, block in normalized_blocks:
                block_type = block.get("type")
                text = _clean_latex(block.get("text") or "")
                score = block.get("score")

                if not text or block_type not in FORMULA_TYPES:
                    continue
                if not _LATEXISH_RE.search(text):
                    continue

                if not isinstance(score, (int, float)) or score < 0.8:
                    continue

                bbox_pdf = image_bbox_to_pdf_bbox(bbox_img, zoom=zoom)
                context = extract_context_from_pdf_words(
                    page,
                    bbox_pdf,
                    context_words=context_words,
                )

                results.append(
                    {
                        "formula_id": formula_counter,
                        "page": page_num,
                        "latex": text,
                        "context": context,
                        "method": "pix2text + pymupdf_text_layer",
                        "confidence": float(score) if isinstance(score, (int, float)) else None,
                    }
                )
                formula_counter += 1
        return results
    finally:
        doc.close()


def write_jsonl(formulas: Sequence[Dict[str, Any]], output_path: str) -> None:
    import json

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in formulas:
            trimmed = {key: item.get(key) for key in FORMULA_KEYS}
            f.write(json.dumps(trimmed, ensure_ascii=False) + "\n")


__all__ = [
    "FormulaExtractionError",
    "Pix2TextNotInstalledError",
    "extract_formulas",
    "is_pix2text_available",
    "write_jsonl",
]
