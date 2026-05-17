# Sprint 5 — Андрей Шумилин

## API формул: финализация и Docker

В Sprint 4 ты добавил `/render` endpoint (LaTeX → PNG через matplotlib) и третий предмет (economic). Сейчас работает, но при попытке запустить у другого человека упадёт из-за одного бага и тяжёлых зависимостей.

## Задачи

### 1) Срочно — добавь matplotlib в `requirements.txt`

В Sprint 4 ты добавил `/render` который использует matplotlib, но забыл прописать его в зависимостях. Без этого `/render` упадёт с `ImportError: No module named matplotlib`.

Открой `formulas/requirements.txt`, в конец допиши:
```
matplotlib
```

### 2) Заверни в Docker

Pix2text тащит ~2GB моделей и требует системные библиотеки (`libgl1`, `libglib2.0-0`). У каждого студента это будет ломаться по-разному. Заверни в Docker, чтобы любой мог поднять одной командой.

Создай `formulas/Dockerfile`:

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Создай `formulas/docker-compose.yml`:

```yaml
services:
  formulas:
    build: .
    ports:
      - "8001:8000"
```

Порт 8001 наружу — внутри контейнера сервис на 8000, но снаружи будет на 8001, чтобы не конфликтовать с сервером Артёма (тоже 8000).

### 3) Pytest-тесты

Создай `formulas/tests/test_app.py` с 5 тестами:

```python
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("render_available") is True

def test_extract_no_pdf():
    r = client.post("/extract", files={"file": ("a.txt", b"hi", "text/plain")})
    assert r.status_code in (400, 415)

def test_render_valid():
    r = client.post("/render", json={"latex": "E=mc^2"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"

def test_render_empty():
    r = client.post("/render", json={"latex": ""})
    assert r.status_code == 400

def test_render_too_long():
    r = client.post("/render", json={"latex": "x" * 600})
    assert r.status_code == 400
```

**Как проверить:** `pytest tests/`

### 4) README

```markdown
# API извлечения и рендеринга формул

- POST /extract — извлекает LaTeX-формулы из PDF
- POST /render — рендерит LaTeX в PNG-картинку
- GET /health — статус сервиса

## Запуск через Docker

docker compose up

Сервис будет доступен на http://localhost:8001

## Примеры

curl http://localhost:8001/health

curl -X POST http://localhost:8001/render \
  -H "Content-Type: application/json" \
  -d '{"latex": "E=mc^2"}' \
  --output formula.png

## Тесты

pytest tests/
```

### 5) Создай PR в main

Сейчас твои изменения Sprint 4 лежат в `main` напрямую (через merge-конфликт). Дальше работаем как все — в ветке `team-andrey`, PR в main, ревью.

## Результат: что лежит в папке

```
formulas/
├── app.py                      # FastAPI приложение
├── formulas_module.py          # из Sprint 3
├── Dockerfile                  # новое
├── docker-compose.yml          # новое
├── requirements.txt            # + matplotlib
├── test_pdfs/                  # PDF для тестов
├── test_results/               # результаты извлечения
├── tests/
│   └── test_app.py             # новое (5 тестов)
└── README.md                   # обновлён
```

## Как проверяется

1. Другой студент клонирует репо
2. В папке `formulas/` запускает `docker compose up` — поднимается без ошибок
3. `curl http://localhost:8001/health` → `{"render_available": true, ...}`
4. `curl -X POST http://localhost:8001/render -H "Content-Type: application/json" -d '{"latex": "E=mc^2"}' --output formula.png` → PNG скачивается
5. `pytest tests/` — все 5 тестов зелёные

## Если застрял

Спрашивай Сергея Романовича.
