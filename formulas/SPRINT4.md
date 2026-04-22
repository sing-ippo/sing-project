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

> **Важно:** matplotlib использует встроенный движок mathtext — он не требует установки LaTeX, но не поддерживает все команды. Сложные конструкции (`\begin{array}`, `\tag`, `\operatorname`) могут не рендериться. В таких случаях возвращай 422 с понятным сообщением об ошибке, не крашь сервер.

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

У тебя уже есть тесты по физике, матану и линалу — это хорошо. Цель Sprint 4 — проверить экстрактор на **принципиально других типах формул**, а не просто на большем количестве файлов по тем же предметам.

**Добавить минимум 1-2 новых предмета с другой нотацией:**
- Химия (если pix2text поддерживает молекулярные формулы)
- Теорвер / статистика (P(A), E[X], σ², распределения)
- Дискретная математика (графы, булева алгебра, комбинаторика)
- Или другой предмет на выбор с заметно другими символами

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
│   ├── physics.pdf             # из Sprint 3
│   ├── matan.pdf               # из Sprint 3
│   ├── linal.pdf               # из Sprint 3
│   └── <новый предмет>.pdf     # новый
├── test_results/
│   ├── physics.jsonl           # из Sprint 3
│   ├── matan.jsonl             # из Sprint 3
│   ├── linal.jsonl             # из Sprint 3
│   └── <новый предмет>.jsonl   # новый
└── README.md                   # обновлён: /render endpoint + результаты тестов
```

## Как проверяется

1. `uvicorn app:app --reload`
2. `GET /health` → `{"render_available": true, ...}`
3. `curl -X POST /render -H "Content-Type: application/json" -d '{"latex": "E=mc^2"}'` → скачивается PNG с формулой
4. `test_results/math.jsonl` содержит извлечённые формулы с confidence > 0.8
5. README описывает результаты по каждому предмету
