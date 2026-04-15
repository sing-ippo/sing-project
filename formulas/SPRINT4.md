# Sprint 4 — Андрей Шумилин

## Рендеринг формул + расширение тестирования

Два направления: новый endpoint для рендеринга LaTeX в изображение, и расширение тестовой базы на разные предметы.

## Часть 1 — Endpoint `/render`

**POST `/render`**

Принимает LaTeX-формулу, возвращает PNG-изображение.

```python
@app.post("/render")
async def render_formula(latex: str = Body(..., embed=True)):
    # latex → PNG через matplotlib
    ...
    return Response(content=png_bytes, media_type="image/png")
```

**Реализация через matplotlib:**

```python
import matplotlib.pyplot as plt
import matplotlib
import io

matplotlib.use('Agg')  # без GUI

def latex_to_png(latex: str, dpi: int = 150) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 1.5))
    ax.axis('off')
    ax.text(0.5, 0.5, f"${latex}$",
            fontsize=20, ha='center', va='center',
            transform=ax.transAxes)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                facecolor='white')
    plt.close(fig)
    return buf.getvalue()
```

**Входные данные:**
```json
{ "latex": "E = mc^2" }
```

**Ответ:** PNG-файл (Content-Type: image/png)

**Валидация:**
- Пустая строка → 400
- Слишком длинная формула (> 500 символов) → 400
- Ошибка рендеринга matplotlib → 422 с описанием

**Обновить `/health`:**
```json
{ "status": "ok", "pix2text_loaded": true, "render_available": true }
```

## Часть 2 — Расширение тестирования

Текущие тесты только на физике (`test_results/physics.jsonl`). Добавить PDF по другим предметам и проверить качество извлечения.

**Добавить минимум 2 новых предмета:**
- Математика (интегралы, производные, матрицы)
- Химия (структурные формулы если поддерживает pix2text) или другой предмет на выбор

**Для каждого нового PDF:**
- Положить в `test_pdfs/`
- Запустить извлечение
- Сохранить результат в `test_results/<предмет>.jsonl`
- Добавить в README краткий вывод: confidence score, сложные случаи

## Результат: что лежит в папке

```
formulas/
├── app.py                      # + endpoint /render
├── formulas_module.py          # без изменений
├── requirements.txt            # + matplotlib
├── test_pdfs/
│   ├── (существующий PDF)
│   ├── math.pdf                # новый
│   └── chemistry.pdf           # новый (или другой)
├── test_results/
│   ├── physics.jsonl           # из Sprint 3
│   ├── math.jsonl              # новый
│   └── chemistry.jsonl         # новый
└── README.md                   # обновлён: /render endpoint + результаты тестов
```

## Как проверяется

1. `uvicorn app:app --reload`
2. `GET /health` → `{"render_available": true, ...}`
3. `curl -X POST /render -H "Content-Type: application/json" -d '{"latex": "E=mc^2"}'` → скачивается PNG с формулой
4. `test_results/math.jsonl` содержит извлечённые формулы с confidence > 0.8
5. README описывает результаты по каждому предмету
