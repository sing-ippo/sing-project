# Sprint 4 — Пётр Жмычков + Кирилл Акишин

## Веб-интерфейс голосового киоска

Вы делаете лицо стенда — то, что видит абитуриент. Красивая веб-страница с кнопкой микрофона, которая записывает голос, отправляет на сервер и показывает ответ.

> Важно: в Sprint 3 от вас не было ни одного коммита. Sprint 4 — возможность это исправить. Ожидается ≥ 3 коммита от каждого участника.

## Что нужно сделать

### Новый файл: `kiosk.html`

Одностраничное веб-приложение (HTML + CSS + JS, без фреймворков).

**Внешний вид:**
- Полноэкранный режим (для монитора стенда)
- Большая кнопка «🎤 Говори» по центру
- Область для текста вопроса (появляется после записи)
- Область для текста ответа (появляется после ответа сервера)
- Анимация во время записи (пульсирующий круг)
- Анимация во время ожидания ответа (спиннер)
- Логотип МИРЭА / кафедры вверху

**Логика (JavaScript):**

```javascript
// 1. Нажать кнопку → начать запись
navigator.mediaDevices.getUserMedia({ audio: true })
  .then(stream => {
    const recorder = new MediaRecorder(stream);
    recorder.start();
    // ... собираем chunks
  });

// 2. Отпустить кнопку → остановить запись → отправить
recorder.stop();
const blob = new Blob(chunks, { type: 'audio/webm' });
const formData = new FormData();
formData.append('audio', blob, 'question.webm');

// 3. POST /ask → показать ответ + проиграть аудио
const response = await fetch('http://localhost:8000/ask', {
  method: 'POST',
  body: formData
});
const data = await response.json();
// показать data.question и data.answer
// проиграть data.audio_base64
```

**Кирилл** — вёрстка и дизайн (HTML/CSS)
**Пётр** — JavaScript логика (MediaRecorder, fetch, воспроизведение аудио)

### Дополнительно: `kiosk_server.py`

Простой HTTP-сервер для раздачи `kiosk.html` (чтобы не открывать файл напрямую):

```python
import http.server
# python kiosk_server.py → http://localhost:3000
```

## Результат: что лежит в папке

```
teacher_pipeline/pipeline/
├── kiosk.html            # веб-интерфейс киоска (новое)
├── kiosk_server.py       # раздаёт kiosk.html на localhost:3000 (новое)
└── README.md             # как запустить (новое)
```

## Как проверяется

1. `python kiosk_server.py` → открыть http://localhost:3000
2. Нажать кнопку → видна анимация записи
3. Отпустить → видна анимация ожидания
4. Появляется текст вопроса и ответа
5. Слышен голосовой ответ из колонки
6. Красиво выглядит на большом экране
