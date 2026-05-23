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