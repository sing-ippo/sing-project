# Sprint 3 — Андрей Шумилин

## REST API для извлечения формул (работа с руководителем)

### Что уже есть (Sprint 1–2)

**Андрей** написал модуль извлечения формул:
- `zxcpix2text.py` (~300 строк) — pix2text + pymupdf
- Извлечение LaTeX из PDF с формулами
- `formulas.jsonl` — реальный вывод с формулами
- `formulas_poc.md` — PoC-отчёт с результатами экспериментов
- Тесты на нескольких PDF с математикой

### Что нового в Sprint 3

Сейчас модуль формул — скрипт, который запускается вручную. Чтобы пайплайн преподавателя мог его вызвать, нужен API: отправляешь PDF → получаешь формулы.

**Новая функциональность:** REST API (FastAPI) для извлечения формул, которое можно вызвать из любого модуля проекта.

### Задание

1. **REST API** на FastAPI:
   - `POST /extract` — принимает PDF-файл (multipart/form-data), возвращает JSON-массив формул в формате formulas.jsonl
   - `POST /extract` с параметром `?pages=1,2,5` — извлечение только с указанных страниц
   - `GET /health` — статус сервиса: `{"status": "ok", "pix2text_loaded": true/false}`
   - Обработка ошибок: не PDF, файл слишком большой, pix2text не установлен

2. **Модуль-обёртка** `formulas_module.py` с функцией из спецификации:
   ```python
   def extract_formulas(pdf_path: str, pages: list[int] = None) -> list[dict]:
   ```
   Формат вывода строго по FORMATS.md: formula_id, page, latex, context, method, confidence.

3. **Тесты** — 3 разных PDF с формулами, сравнение результатов.

4. **Документация** — README с инструкцией запуска + requirements.txt.

### Результат: что лежит в папке

```
formulas/
├── app.py                # FastAPI-сервер
├── formulas_module.py    # Модуль с extract_formulas()
├── requirements.txt      # pix2text, fastapi, uvicorn, pymupdf, python-multipart
├── test_pdfs/            # 3 тестовых PDF с формулами
│   ├── calculus.pdf
│   ├── linear_algebra.pdf
│   └── physics.pdf
├── test_results/         # Результаты извлечения
│   ├── calculus_formulas.jsonl
│   ├── linear_algebra_formulas.jsonl
│   └── physics_formulas.jsonl
└── README.md             # Установка, запуск, примеры curl-запросов
```

### Как будет проверяться

1. `pip install -r requirements.txt && uvicorn app:app` — сервер запускается
2. `curl http://localhost:8000/health` → `{"status": "ok", ...}`
3. `curl -X POST -F "file=@test_pdfs/calculus.pdf" http://localhost:8000/extract` → JSON с формулами
4. Каждая формула содержит все 6 полей из FORMATS.md
5. test_results/ содержит результаты для всех 3 PDF
6. `from formulas_module import extract_formulas` работает как импорт

### Чекпоинт — среда 20:00

`[Андрей] PR: <ссылка> — API работает / extract_formulas() готов / в процессе`
