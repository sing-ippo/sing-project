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