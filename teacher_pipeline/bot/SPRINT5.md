# Sprint 5 — Павел Чернов + Спартак Петросян

## Telegram-бот преподавателя: финализация

В Sprint 4 вы добавили команду `/quiz_faq <категория>` для генерации квиза из общей базы. Сейчас бот работает, но критичные проблемы из ревью Sprint 3 надо окончательно закрыть.

## Павел — `pipeline.py`

### 1) Проверь отсутствие хардкода прокси

В Sprint 4 эту проблему вроде починили — теперь прокси читается из `.env`. Но проверь что в `pipeline.py` нигде не осталось строк типа:
```python
PROXY_URL = 'http://127.0.0.1:10809'  # БЫЛО — удали если осталось
os.environ['HTTP_PROXY'] = PROXY_URL
```

Прокси нужен только для Telegram API (в `teacher_bot.py`), Gemini API из России работает без прокси.

### 2) Graceful error при недоступном Gemini

Если у проверяющего не будет VPN или неверный API-ключ, твоя функция должна вернуть понятное сообщение, а не упасть с traceback:

```python
def generate_quiz_from_faq(entries, num_questions=5):
    try:
        response = model.generate_content(prompt)
        return parse_quiz(response.text)
    except Exception as e:
        return {"error": f"Не удалось сгенерировать квиз: {str(e)}"}
```

Бот Спартака потом проверит на ключ `error` и покажет сообщение преподавателю.

### 3) `requirements.txt`

Добавь все библиотеки которые реально используешь. НЕ делай `pip freeze` со всеми 150 пакетами твоей системы — только то что импортируется в `pipeline.py` и `teacher_bot.py`. Минимум:
```
google-generativeai
python-dotenv
python-telegram-bot
pypdf
python-docx
httpx
```

## Спартак — `teacher_bot.py` и безопасность

### 1) Перевыпусти токен бота

Старый `.env` файл был запушен в git в Sprint 3 — токен мог утечь.

1. Telegram → @BotFather → команда `/mybots`
2. Выбери своего бота → `API Token` → `Revoke current token`
3. BotFather выдаст новый токен — скопируй его
4. Положи в файл `.env` рядом с `teacher_bot.py`:
   ```
   TELEGRAM_TOKEN=твой_новый_токен_здесь
   GEMINI_API_KEY=ключ_от_gemini
   PROXY_URL=
   ```

**КАТЕГОРИЧЕСКИ НЕ ДОБАВЛЯЙ `.env` в git.**

### 2) Проверь `.gitignore`

В папке `teacher_pipeline/bot/` должен быть `.gitignore`. Если файла нет — создай. Должно быть минимум:
```
.env
downloads/
__pycache__/
*.pyc
```

**Как проверить:** запусти `git status`. Файл `.env` НЕ должен быть в списке «untracked files». Если он там — значит `.gitignore` не работает.

### 3) Создай `.env.example`

Это шаблон без реальных значений, его коммитим в git:
```
TELEGRAM_TOKEN=
GEMINI_API_KEY=
PROXY_URL=
```

Другие студенты увидят какие переменные нужны.

### 3a) Удали мусорный файл `team-pavel-spartak`

В папке `teacher_pipeline/bot/` лежит пустой файл с именем `team-pavel-spartak` (случайно создан, имя ветки). Удали его:
```bash
git rm teacher_pipeline/bot/team-pavel-spartak
```

### 4) README

```markdown
# Telegram-бот для преподавателей

Принимает PDF/TXT с лекцией, генерирует тест через Gemini API.
Команда /quiz_faq <категория> делает квиз из общей базы FAQ.

## Что нужно

1. **Telegram-бот.** Создай в @BotFather (команда /newbot), скопируй токен.
2. **Ключ Gemini API.** Получи на https://aistudio.google.com/apikey (нужен VPN при первом получении).

## Установка

pip install -r requirements.txt
cp .env.example .env
# Открой .env, вставь свои токен и ключ

## Запуск

python teacher_bot.py

## Использование

В Telegram найди своего бота, отправь:
- PDF/TXT файл → получи квиз по нему
- /quiz_faq экзамены → квиз по категории из общей базы FAQ
```

## Результат: что лежит в папке

```
teacher_pipeline/bot/
├── teacher_bot.py        # хэндлеры Telegram (Спартак)
├── pipeline.py           # генерация квизов (Павел)
├── requirements.txt
├── .env.example          # шаблон переменных
├── .gitignore            # .env, downloads/
└── README.md
```

## Как проверяется

1. Другой студент клонирует репо
2. Создаёт своего бота в BotFather, получает токен
3. Получает ключ Gemini
4. `cp .env.example .env`, заполняет значения
5. `pip install -r requirements.txt`
6. `python teacher_bot.py` — бот стартует без ошибок
7. В Telegram отправляет PDF → получает квиз
8. Команда `/quiz_faq экзамены` → получает квиз из FAQ

## Если застрял

Спрашивайте друг друга или Сергея Романовича.
