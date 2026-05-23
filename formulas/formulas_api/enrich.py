"""Обогащение формул названиями/пояснениями через DeepSeek и экспорт в .docx (OMML) через pandoc."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import httpx

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

_SYSTEM_PROMPT = (
    "Ты помогаешь преподавателю каталогизировать формулы из учебного документа. "
    "Тебе дают список формул (LaTeX + контекст из документа). Для КАЖДОЙ формулы верни: "
    "name — краткое русское название (например «Теорема Пифагора», «Производная произведения»); "
    "description — 1-2 предложения, что это и где применяется; "
    "latex — исходный LaTeX, при необходимости исправленный (валидный). "
    "Верни СТРОГО JSON-массив объектов {id, name, description, latex} без markdown и текста вне JSON."
)


def _extract_json_array(raw: str) -> List[Dict[str, Any]]:
    if not raw:
        return []
    start, end = raw.find("["), raw.rfind("]") + 1
    if start == -1 or end == 0:
        return []
    try:
        data = json.loads(raw[start:end])
        return data if isinstance(data, list) else []
    except Exception:
        return []


def name_formulas(formulas: List[Dict[str, Any]], source_title: str = "") -> List[Dict[str, Any]]:
    """Добавляет name/description и исправленный latex через DeepSeek (один батч-запрос).
    Без ключа или при ошибке возвращает формулы как есть (с пустыми name/description)."""
    if not formulas:
        return formulas
    if not DEEPSEEK_API_KEY:
        for f in formulas:
            f.setdefault("name", "")
            f.setdefault("description", "")
        return formulas

    items = [
        {"id": f["formula_id"], "latex": f.get("latex", ""), "context": (f.get("context") or "")[:300]}
        for f in formulas
    ]
    user_msg = (
        f"Документ: {source_title}\n\nФормулы:\n" + json.dumps(items, ensure_ascii=False)
    )
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    try:
        resp = httpx.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=60.0)
        resp.raise_for_status()
        named = _extract_json_array(resp.json()["choices"][0]["message"]["content"])
    except Exception:
        named = []

    by_id = {n.get("id"): n for n in named if isinstance(n, dict)}
    for f in formulas:
        n = by_id.get(f["formula_id"], {})
        f["name"] = (n.get("name") or "").strip()
        f["description"] = (n.get("description") or "").strip()
        fixed = (n.get("latex") or "").strip()
        if fixed:
            f["latex"] = fixed
    return formulas


def formulas_to_docx(formulas: List[Dict[str, Any]], title: str = "Формулы") -> bytes:
    """Собирает .docx с нативными уравнениями OMML через pandoc (markdown → docx)."""
    lines = [f"# Формулы: {title}", ""]
    for i, f in enumerate(formulas, start=1):
        name = (f.get("name") or f"Формула {i}").strip()
        latex = (f.get("latex") or "").strip()
        lines.append(f"## {name}")
        lines.append("")
        if latex:
            lines.append(f"$${latex}$$")
            lines.append("")
    md = "\n".join(lines)

    tmpdir = tempfile.mkdtemp()
    md_path = Path(tmpdir) / "formulas.md"
    docx_path = Path(tmpdir) / "formulas.docx"
    md_path.write_text(md, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["pandoc", str(md_path), "-o", str(docx_path)],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0 or not docx_path.exists():
            raise RuntimeError(f"pandoc: {proc.stderr.strip()[:200]}")
        return docx_path.read_bytes()
    finally:
        for p in (md_path, docx_path):
            if p.exists():
                p.unlink()
        os.rmdir(tmpdir)
