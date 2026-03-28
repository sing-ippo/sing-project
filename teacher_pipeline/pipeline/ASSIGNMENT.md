# Sprint 3 — Пётр Жмычков + Кирилл Акишин

## Связанный пайплайн: chunking → quiz с привязкой к чанкам

### Что уже есть (Sprint 1–2)

**Кирилл** написал `chanked_text.py`:
- Нарезка текста через langchain RecursiveCharacterTextSplitter
- Поддержка .txt и .pdf (pymupdf)
- Вывод: список dict с chunk_id, source, text, word_count
- Не хватает: полей page и overlap_prev, вывода в JSONL, функции-интерфейса по спецификации

**Пётр** написал `quiz_generator.py`:
- Генерация через Groq API (LLaMA 3.3 70B)
- Промпт на русском, JSON-ответ
- API-ключ через .env (python-dotenv)
- Не хватает: поля source_chunk_id в вопросах, приёма чанков (а не сырого текста)

### Что нового в Sprint 3

Сейчас модули работают изолированно: Кирилл нарезает текст, Пётр генерирует квиз из сырого текста — между ними нет связи. Если студент видит вопрос в квизе, он не знает, из какого куска лекции этот вопрос.

**Новая функциональность:** пайплайн, в котором квиз привязан к чанкам. Каждый вопрос содержит `source_chunk_id` — можно перейти от вопроса к конкретному фрагменту лекции.

1. **Chunk-aware quiz** — quiz_module принимает список чанков (не сырой текст) и генерирует вопросы per-chunk, проставляя source_chunk_id.

2. **Верификация связности** — скрипт verify.py проверяет, что все source_chunk_id из quiz.json реально существуют в chunks.jsonl.

3. **Два тестовых прогона** — пайплайн протестирован на двух разных файлах, результаты в папках output_1/ и output_2/.

### Кто что делает

**Кирилл:**
- Переписать chunk-модуль в `chunk_module.py` с правильным интерфейсом:
  ```python
  def chunk_file(file_path: str, chunk_size: int = 400, overlap: int = 50) -> list[dict]:
  ```
  - Выход: все 6 полей из FORMATS.md — chunk_id, source, page, text, word_count, overlap_prev
  - page: номер страницы для PDF (через pymupdf), None для .txt
  - overlap_prev: True если чанк начинается с перекрытия
  - Можно оставить langchain или переписать вручную — главное чтобы интерфейс и формат были по спеке
- Функция `save_chunks(chunks, path)` → сохранение в JSONL
- CLI: `python chunk_module.py lecture.pdf` → выводит chunks.jsonl

**Пётр:**
- Доработать quiz-модуль в `quiz_module.py`:
  ```python
  def generate_quiz(chunks: list[dict], num_questions: int = 10) -> list[dict]:
  ```
  - Принимает СПИСОК ЧАНКОВ (не сырой текст)
  - Для каждого чанка генерирует 1–3 вопроса (зависит от длины)
  - Каждый вопрос содержит `source_chunk_id` = chunk_id того чанка, из которого он сгенерирован
  - Fallback: если Groq API недоступен → демо-генерация (как в прототипе)
  - API-ключ только через .env
- Функция `save_quiz(quiz, path)` → сохранение в JSON

**Вместе:**
- `pipeline.py` — CLI: `python pipeline.py --input lecture.pdf --output ./output/`
  - Шаг 1: chunk_module.chunk_file(input) → chunks
  - Шаг 2: quiz_module.generate_quiz(chunks) → quiz
  - Шаг 3: сохранить chunks.jsonl + quiz.json в output/
- `verify.py` — проверка связности:
  - Читает chunks.jsonl и quiz.json из одной папки
  - Проверяет: каждый source_chunk_id из quiz.json существует в chunks.jsonl
  - Вывод: «OK, все 15 вопросов привязаны к существующим чанкам» или «ОШИБКА: вопрос 7 ссылается на chunk_id 99, которого нет»

### Результат: что лежит в папке

```
teacher_pipeline/pipeline/
├── pipeline.py           # CLI: python pipeline.py --input ... --output ...
├── chunk_module.py       # Нарезка документов (Кирилл)
├── quiz_module.py        # Генерация квиза (Пётр)
├── verify.py             # Проверка связности quiz ↔ chunks
├── output_1/             # Тестовый прогон 1
│   ├── chunks.jsonl
│   └── quiz.json
├── output_2/             # Тестовый прогон 2
│   ├── chunks.jsonl
│   └── quiz.json
├── test_files/           # Входные файлы для тестов
│   ├── lecture1.txt
│   └── lecture2.txt      # (или .pdf)
├── .env.example          # GROQ_API_KEY=your_key_here
└── README.md             # Установка, запуск, примеры
```

### Как будет проверяться

1. `python pipeline.py --input test_files/lecture1.txt --output ./test_out/` — выполняется без ошибок
2. Открываю `test_out/chunks.jsonl` — каждая строка содержит все 6 полей: chunk_id, source, page, text, word_count, overlap_prev
3. Открываю `test_out/quiz.json` — каждый вопрос содержит source_chunk_id, и это число (не null)
4. `python verify.py ./test_out/` → «OK»
5. `python verify.py ./output_1/` → «OK» (предоставленный тестовый прогон)
6. `python verify.py ./output_2/` → «OK» (второй тестовый прогон)
7. В output_1 и output_2 — разные файлы (не копия одного и того же)
8. В git-истории коммиты от Кирилла И от Петра (≥ 3 от каждого)

### Чекпоинт — среда 20:00

`[Пётр + Кирилл] PR: <ссылка> — chunk_module готов / quiz принимает чанки / в процессе`
