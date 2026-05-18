# Sprint 5 — Пётр Жмычков + Кирилл Акишин

## Фронт голосового киоска

В Sprint 3 и Sprint 4 от вас не было ни одного коммита. **Это ваш последний шанс сдать что-то за семестр.**

Делаете одностраничное веб-приложение — фронт голосового киоска для ДОД. Кирилл — вёрстка и CSS, Пётр — JavaScript логика.

> **Если за неделю (к 24 мая) не появится ни одного коммита** — фронт-заглушку соберёт за вас другой студент, но тогда оценка за семестр у вас обоих будет под вопросом. Если что-то непонятно — пишите в чат **сегодня**, не молчите две недели.

## Кирилл — HTML, CSS и сервер

### 1) HTML-структура `kiosk.html`

Создай файл `teacher_pipeline/pipeline/kiosk.html`. Минимальная разметка которую Пётр оживит JS-ом:

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Голосовой ассистент МИРЭА</title>
    <link rel="stylesheet" href="kiosk.css">
</head>
<body>
    <header>
        <img src="logo.png" alt="МИРЭА">
    </header>

    <main>
        <button id="record-btn">🎤 Говори</button>
        <div id="question"></div>
        <div id="answer"></div>
    </main>

    <script src="kiosk.js"></script>
</body>
</html>
```

`logo.png` положи в ту же папку — можно скачать с сайта МИРЭА.

### 2) CSS — файл `kiosk.css`

Стенд работает на большом мониторе, не телефоне. Шрифты крупные, всё центрировано:

```css
body {
    margin: 0;
    font-family: sans-serif;
    background: #f0f4f8;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

header {
    padding: 20px;
    text-align: center;
}

header img {
    height: 60px;
}

main {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 30px;
}

#record-btn {
    width: 250px;
    height: 250px;
    border-radius: 50%;
    border: none;
    background: #2196f3;
    color: white;
    font-size: 32px;
    cursor: pointer;
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}

#record-btn.recording {
    background: #f44336;
    animation: pulse 1s infinite;
}

#record-btn.loading {
    background: #ff9800;
    animation: spin 1s linear infinite;
}

@keyframes pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.1); }
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

#question, #answer {
    font-size: 28px;
    max-width: 800px;
    text-align: center;
    padding: 20px;
}

#question { color: #555; }
#answer { color: #222; font-weight: bold; }
```

### 3) `kiosk_server.py`

Простой сервер для раздачи страницы. Нужен потому что если открыть `kiosk.html` двойным кликом (через `file://`), браузер заблокирует микрофон по соображениям безопасности.

```python
import http.server
import socketserver
import os

PORT = 3000
os.chdir(os.path.dirname(os.path.abspath(__file__)))

with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    print(f"Открой в браузере: http://localhost:{PORT}/kiosk.html")
    httpd.serve_forever()
```

## Пётр — JavaScript логика

Создай файл `teacher_pipeline/pipeline/kiosk.js`. Вот рабочий скелет — скопируй и доработай:

```javascript
// === Настройки ===
const BACKEND_URL = "http://localhost:8000"; // адрес сервера Артёма+Льва

// === Глобальные переменные ===
let mediaRecorder = null;
let audioChunks = [];

// === Запись голоса ===
async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
        mediaRecorder.onstop = () => sendAudio();

        mediaRecorder.start();
        document.getElementById('record-btn').classList.add('recording');
    } catch (err) {
        alert('Не удалось получить доступ к микрофону: ' + err.message);
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        const btn = document.getElementById('record-btn');
        btn.classList.remove('recording');
        btn.classList.add('loading');
    }
}

// === Отправка на сервер ===
async function sendAudio() {
    const blob = new Blob(audioChunks, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('file', blob, 'question.webm');

    try {
        const response = await fetch(`${BACKEND_URL}/ask`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Сервер вернул ${response.status}`);
        }

        const data = await response.json();
        showResult(data);
    } catch (err) {
        document.getElementById('answer').textContent =
            'Сервис временно недоступен. Попробуйте ещё раз.';
        console.error(err);
    } finally {
        document.getElementById('record-btn').classList.remove('loading');
    }
}

// === Показ результата ===
function showResult(data) {
    document.getElementById('question').textContent = data.question || '';
    document.getElementById('answer').textContent = data.answer || '';

    if (data.audio_base64) {
        const audioBlob = base64ToBlob(data.audio_base64, 'audio/wav');
        const audioUrl = URL.createObjectURL(audioBlob);
        new Audio(audioUrl).play();
    }
}

// === Утилита: base64 → Blob ===
function base64ToBlob(base64, mimeType) {
    const byteChars = atob(base64);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
        byteNumbers[i] = byteChars.charCodeAt(i);
    }
    return new Blob([new Uint8Array(byteNumbers)], { type: mimeType });
}

// === Привязка к кнопке ===
const btn = document.getElementById('record-btn');
btn.addEventListener('mousedown', startRecording);
btn.addEventListener('mouseup', stopRecording);
btn.addEventListener('touchstart', startRecording);
btn.addEventListener('touchend', stopRecording);
```

## Как тестировать

Без сервера Артёма+Льва ничего не отправится. Подними его сервер у себя:

1. Перейди в папку `student_assistant/bot/`
2. Следуй инструкциям из их README (установить ffmpeg, `pip install -r requirements.txt`, `uvicorn voice_server:app`)
3. Сервер должен запуститься на `http://localhost:8000`
4. Теперь в другом терминале — `python kiosk_server.py` в вашей папке (на localhost:3000)
5. Открой `http://localhost:3000/kiosk.html` в браузере
6. Нажми кнопку, скажи что-нибудь, отпусти — должен прийти ответ

## README в `teacher_pipeline/pipeline/`

```markdown
# Фронт голосового киоска

Веб-страница с большой кнопкой «Говори»: записывает голос, отправляет на сервер ассистента, проигрывает голосовой ответ.

## Запуск

python kiosk_server.py

Откроется на http://localhost:3000/kiosk.html

## Важно

Перед запуском должен быть запущен сервер ассистента на localhost:8000 (см. `student_assistant/bot/README.md`).
```

## Результат: что лежит в папке

```
teacher_pipeline/pipeline/
├── kiosk.html            # разметка (Кирилл)
├── kiosk.css             # стили (Кирилл)
├── kiosk.js              # логика (Пётр)
├── kiosk_server.py       # раздаёт страницу (Кирилл)
├── logo.png              # логотип МИРЭА
└── README.md
```

## Как проверяется

1. Другой студент запускает сервер Артёма+Льва на localhost:8000
2. В папке `teacher_pipeline/pipeline/` запускает `python kiosk_server.py`
3. Открывает `http://localhost:3000/kiosk.html`
4. Видит большую кнопку «Говори», полноэкранную
5. Нажимает → видна красная пульсация (запись)
6. Отпускает → видна оранжевая крутилка (ожидание)
7. Появляется текст вопроса и ответа, играет голосовой ответ

## Если застрял

- Пётр — спрашивай Артёма за форматом API (`/ask`)
- Кирилл — спрашивай Петра за вёрсткой
- Оба — Сергея Романовича

**Не молчите.** Пишите в чат сразу как застряли.
