# Git-инструкция для участников СИНГ

## Первоначальная настройка (один раз)

### 1. Установи Git
- Windows: скачай с [git-scm.com](https://git-scm.com/download/win), установи с настройками по умолчанию
- Mac: `brew install git` или скачай с git-scm.com
- Linux: `sudo apt install git`

### 2. Настрой имя и почту
```bash
git config --global user.name "Имя Фамилия"
git config --global user.email "твоя@почта.com"
```

### 3. Создай аккаунт на GitHub
Зайди на [github.com](https://github.com) и зарегистрируйся (если ещё нет аккаунта).

### 4. Клонируй репозиторий
```bash
git clone https://github.com/<org>/sing-project.git
cd sing-project
```

## Рабочий процесс (каждый день)

### Шаг 1: Обнови main
```bash
git checkout main
git pull
```

### Шаг 2: Создай свою ветку (один раз на спринт)
```bash
git checkout -b team-artem-lev
```
Название ветки — имена пары через дефис: `team-artem-lev`, `team-vitya-sasha`, `team-petr-kirill`, `team-pavel-spartak`, `team-makar`, `team-andrey`.

Если ветка уже создана:
```bash
git checkout team-artem-lev
```

### Шаг 3: Работай в СВОЕЙ папке
Каждая пара работает только в своей папке. Не трогай чужие файлы.

| Пара | Папка |
|---|---|
| Артём + Лев | `student_assistant/bot/` |
| Витя + Саша | `student_assistant/data/` |
| Пётр + Кирилл | `teacher_pipeline/pipeline/` |
| Павел + Спартак | `teacher_pipeline/bot/` |
| Макар | `analytics/` |
| Андрей | `formulas/` |

### Шаг 4: Сохрани изменения (коммит)
```bash
git add student_assistant/bot/    # свою папку
git commit -m "feat: добавил inline-кнопки обратной связи"
git push -u origin team-artem-lev
```

Первый `push` с флагом `-u`, дальше просто `git push`.

### Шаг 5: Создай Pull Request
1. Зайди на GitHub в репозиторий
2. Увидишь баннер «team-artem-lev had recent pushes» → нажми **Compare & pull request**
3. Заполни:
   - Title: что сделали (кратко)
   - Description: кто что сделал, как запустить
4. Нажми **Create pull request**
5. Дождись ревью от руководителя

## Правила коммитов

Формат: `тип: описание`

| Тип | Когда |
|---|---|
| `feat` | Новая функциональность |
| `fix` | Исправление бага |
| `docs` | Документация, README |
| `refactor` | Рефакторинг без нового функционала |
| `test` | Тесты |

Примеры:
```
feat: добавил кнопки Да/Нет после ответа бота
fix: исправил кодировку в chunks.jsonl
docs: написал README с инструкцией запуска
refactor: вынес валидацию в отдельный модуль
```

## Частые ситуации

### Хочу посмотреть что изменилось
```bash
git status          # какие файлы изменены
git diff            # что именно изменилось
git log --oneline   # история коммитов
```

### Партнёр запушил, хочу получить его изменения
```bash
git pull origin team-artem-lev
```

### Случайно изменил чужой файл
```bash
git checkout -- путь/к/чужому/файлу
```

### Конфликт при pull
Если Git пишет CONFLICT — откройте файл, найдите строки с `<<<<<<<` и `>>>>>>>`, выберите нужный вариант, удалите маркеры, сохраните, затем:
```bash
git add .
git commit -m "fix: resolved merge conflict"
```

Если совсем запутались — напишите руководителю.

## Чего НЕ делать

- **Не коммитьте `.env` файлы** — там секреты (API-ключи, токены)
- **Не работайте в чужих папках** — только в своей
- **Не делайте `git push --force`** — это перезаписывает историю
- **Не коммитьте `__pycache__/`** — он в .gitignore
