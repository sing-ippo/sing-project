# Telegram-бот для преподавателей

Telegram-бот для генерации квизов по лекциям и базе FAQ с использованием Gemini API.

## Возможности

- Генерация тестов по PDF/TXT файлам
- Квиз по общей базе FAQ
- Фильтрация FAQ по категориям и темам
- Telegram-интерфейс с кнопками
- Поддержка Gemini API

---

## Структура проекта

```text
teacher_pipeline/bot/
├── teacher_bot.py        # Telegram-бот
├── pipeline.py           # Генерация квизов
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Что нужно

### 1. Telegram-бот

Создай бота через @BotFather:

```text
/newbot
```

Скопируй токен.

---

### 2. Gemini API Key

Получи API-ключ:

https://aistudio.google.com/apikey

VPN может понадобиться только при первом получении ключа.

---

## Установка

### 1. Клонировать репозиторий

```bash
git clone <repo_url>
cd teacher_pipeline/bot
```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

### 3. Создать .env

Скопируй шаблон:

```bash
cp .env.example .env
```

Заполни `.env`:

```env
TELEGRAM_TOKEN=your_token
GEMINI_API_KEY=your_key
PROXY_URL=
```

---

## Запуск

```bash
python teacher_bot.py
```

После запуска бот появится в Telegram.

---

## Использование

### TXT/PDF

Отправь боту TXT или PDF файл с лекцией — бот создаст квиз автоматически.

### FAQ-квиз

```text
/quiz_faq <категория>
```

Пример:

```text
/quiz_faq Python
```

### Выбор категории и темы

```text
/categories
```

Бот покажет:
- категории
- темы
- квиз по выбранной теме

---

## Используемые технологии

- Python
- python-telegram-bot
- Gemini API
- python-dotenv
- pypdf
- python-docx
