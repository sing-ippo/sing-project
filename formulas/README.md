## Установка

```bash
pip install -r requirements.txt
```

## Запуск сервера

```bash
uvicorn app:app --reload
```

Проверка healthcheck:

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:

```json
{"status": "ok", "pix2text_loaded": true}
```

Если `pix2text` не установлен или не смог загрузиться, ответ будет:

```json
{"status": "ok", "pix2text_loaded": false}
```

## API

### `GET /health`
Возвращает статус сервиса:

```json
{"status": "ok", "pix2text_loaded": true}
```

### `POST /extract`
Принимает PDF через `multipart/form-data` и возвращает массив формул.

Пример:

```bash
curl -X POST -F "file=@test_pdfs/calculus.pdf" http://localhost:8000/extract
```

### `POST /extract?pages=1,2,5`
Извлечение только с указанных страниц.

```bash
curl -X POST \
  -F "file=@test_pdfs/physics.pdf" \
  "http://localhost:8000/extract?pages=1,2"
```

## Формат ответа

Каждый объект формулы содержит строго 6 полей:

- `formula_id`
- `page`
- `latex`
- `context`
- `method`
- `confidence`

Пример:

```json
[
  {
    "formula_id": 1,
    "page": 1,
    "latex": "f'(x) = 3x^2",
    "context": "Derivative example for the polynomial function ...",
    "method": "pix2text + pymupdf_text_layer",
    "confidence": 0.98
  }
]
```

## Обработка ошибок

- не PDF → `400`
- битый PDF → `400`
- слишком большой файл → `413`
- `pix2text` не установлен → `503`
- внутренняя ошибка извлечения → `500`

## Использование как модуля

```python
from formulas_module import extract_formulas

formulas = extract_formulas("test_pdfs/linal.pdf")
print(formulas)
```

С выбором страниц:

```python
formulas = extract_formulas("test_pdfs/physics.pdf", pages=[1, 2])
```

