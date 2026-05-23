from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")  # without GUI
import matplotlib.pyplot as plt
from fastapi import Body, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from formulas_api.formulas_module import (
    FormulaExtractionError,
    Pix2TextNotInstalledError,
    extract_any,
    extract_formulas,
    is_pix2text_available,
)

app = FastAPI(title="Formula Extractor API", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_LATEX_LENGTH = 500


def parse_pages_param(pages: Optional[str]) -> list[int] | None:
    if not pages:
        return None

    result: list[int] = []
    for raw in pages.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if not raw.isdigit():
            raise HTTPException(
                status_code=400,
                detail="Invalid pages parameter. Use comma-separated positive integers.",
            )

        page_num = int(raw)
        if page_num <= 0:
            raise HTTPException(status_code=400, detail="Page numbers must be positive integers.")
        result.append(page_num)

    if not result:
        raise HTTPException(status_code=400, detail="No valid page numbers provided.")

    return result


def latex_to_png(latex: str, dpi: int = 150) -> bytes:
    """Render a LaTeX formula to PNG bytes using matplotlib mathtext."""
    fig, ax = plt.subplots(figsize=(6, 1.5))
    try:
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            f"${latex}$",
            fontsize=20,
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=dpi,
            bbox_inches="tight",
            facecolor="white",
        )
        return buf.getvalue()
    finally:
        plt.close(fig)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "pix2text_loaded": is_pix2text_available(),
        "render_available": True,
    }


@app.post("/render")
async def render_formula(latex: str = Body(..., embed=True)) -> Response:
    if latex is None:
        raise HTTPException(status_code=400, detail="LaTeX formula is required.")

    latex = latex.strip()
    if not latex:
        raise HTTPException(status_code=400, detail="LaTeX formula must not be empty.")

    if len(latex) > MAX_LATEX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"LaTeX formula is too long. Max length is {MAX_LATEX_LENGTH} characters.",
        )

    try:
        png_bytes = latex_to_png(latex)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "Failed to render LaTeX with matplotlib mathtext. "
                "The formula may be invalid or use unsupported commands "
                "(for example: \\begin{array}, \\tag, \\operatorname). "
                f"Details: {exc}"
            ),
        ) from exc

    return Response(content=png_bytes, media_type="image/png")


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    """Извлекает формулы из документа любого поддерживаемого типа:
    PDF и картинки (png/jpg) — через pix2text; docx — через pandoc; txt/md/tex — регуляркой."""
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Файл слишком большой. Лимит {MAX_FILE_SIZE} байт.")
    if not data:
        raise HTTPException(status_code=400, detail="Пустой файл.")

    suffix = Path(file.filename or "upload").suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        formulas = extract_any(tmp_path, file.filename or tmp_path)
        return JSONResponse(content=formulas)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Pix2TextNotInstalledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FormulaExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)
