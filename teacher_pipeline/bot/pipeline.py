import argparse
import json
import os
from typing import Any, Dict, List
from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")

def load_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def load_pdf(path: str) -> str:
    try:
        import PyPDF2
    except ImportError:
        print("[Ошибка] Не установлена библиотека: pip install PyPDF2")
        return ""

    text = ""
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception as e:
        print(f"[Ошибка] Чтение PDF: {e}")
    return text

def load_docx(path: str) -> str:
    try:
        import docx
    except ImportError:
        print("[Ошибка] Не установлена библиотека: pip install python-docx")
        return ""

    try:
        doc = docx.Document(path)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        print(f"[Ошибка] Чтение DOCX: {e}")
        return ""

def load_document(path: str) -> str:
    if not os.path.exists(path):
        print(f"[!] Файл не найден: {path}")
        return ""

    max_size = 50 * 1024
    file_size = os.path.getsize(path)
    if file_size > max_size:
        print(f"[!] Файл слишком большой ({file_size} байт). Лимит — 50 KB.")
        return ""

    lower_path = path.lower()
    if not (lower_path.endswith(".txt") or lower_path.endswith(".pdf") or lower_path.endswith(".docx")):
        print("[!] Формат не поддерживается (.txt, .pdf, .docx)")
        return ""

    text = ""
    if lower_path.endswith(".txt"):
        text = load_txt(path)
    elif lower_path.endswith(".pdf"):
        text = load_pdf(path)
    elif lower_path.endswith(".docx"):
        text = load_docx(path)

    if not text or not text.strip():
        print("[!] Файл пустой или не содержит извлекаемого текста.")
        return ""

    return text

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[Dict[str, Any]]:
    words = text.split()
    chunks: List[Dict[str, Any]] = []
    start = 0
    chunk_id = 0

    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append({"id": chunk_id, "text": " ".join(chunk_words)})
        start += chunk_size - overlap
        chunk_id += 1

    return chunks

def save_chunks(chunks: List[Dict[str, Any]], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

def _get_gemini_client():
    try:
        from google import genai
    except ImportError:
        print("[Ошибка] Не установлена библиотека: pip install google-generativeai")
        return None

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[Ошибка] Переменная GEMINI_API_KEY не задана.")
        return None

    return genai.Client(api_key=api_key)

def _extract_json_array(raw_text: str) -> List[Dict[str, Any]]:
    if not raw_text:
        return []

    start = raw_text.find("[")
    end = raw_text.rfind("]") + 1
    if start == -1 or end == 0:
        return []

    try:
        data = json.loads(raw_text[start:end])
    except Exception:
        return []

    if isinstance(data, list):
        return data
    return []

def _normalize_quiz(quiz: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []

    for idx, item in enumerate(quiz, start=1):
        if not isinstance(item, dict):
            continue

        normalized.append({
            "id": item.get("id", idx),
            "question": item.get("question", ""),
            "options": item.get("options", []),
            "correct": item.get("correct", 0),
            "explanation": item.get("explanation", ""),
            "source_chunk_id": item.get("source_chunk_id", None),
        })

    return normalized

def generate_quiz(text: str, num_questions: int = 5) -> List[Dict[str, Any]]:
    client = _get_gemini_client()
    if client is None:
        return []

    prompt = f"""
Создай {num_questions} тестовых вопросов по тексту.

Требования:
- Верни строго JSON-массив.
- Каждый объект должен содержать поля:
  id, question, options, correct, explanation, source_chunk_id.
- question и explanation должны быть на русском языке.
- options — список из 4 вариантов ответа.
- correct — индекс правильного ответа: 0, 1, 2 или 3.
- source_chunk_id — это id чанка из текста вида [ID:<номер>]. Если определить нельзя, поставь null.
- Не добавляй markdown, комментарии или пояснения вне JSON.

Текст:
{text}
"""

    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        quiz = _extract_json_array(getattr(response, "text", ""))
        if not quiz:
            print("[Ошибка] Нейросеть вернула пустой или некорректный JSON.")
            return []
        return _normalize_quiz(quiz)
    except Exception as e:
        print(f"[Ошибка] Нейросеть не смогла создать квиз: {e}")
        return []

def generate_quiz_from_faq(entries: list, num_questions: int = 5) -> List[Dict[str, Any]]:
    """
    Принимает список FAQ-записей и возвращает квиз в том же формате,
    что и generate_quiz().
    """
    if not entries:
        print("[!] FAQ-записи не переданы.")
        return []

    prepared_entries = []
    for idx, entry in enumerate(entries, start=1):
        if isinstance(entry, dict):
            category = entry.get("category", "")
            question = entry.get("question", entry.get("q", ""))
            answer = entry.get("answer", entry.get("a", ""))
            prepared_entries.append(
                f"Запись {idx}\nКатегория: {category}\nВопрос: {question}\nОтвет: {answer}"
            )
        else:
            prepared_entries.append(f"Запись {idx}: {str(entry)}")

    faq_context = "\n\n".join(prepared_entries)
    client = _get_gemini_client()
    if client is None:
        return []

    prompt = f"""
На основе этих FAQ-вопросов и ответов составь {num_questions} тестовых вопросов для студентов.

Требования:
- Верни строго JSON-массив.
- Каждый объект должен содержать поля:
  id, question, options, correct, explanation, source_chunk_id.
- question и explanation должны быть на русском языке.
- options — список из 4 вариантов ответа.
- correct — индекс правильного ответа: 0, 1, 2 или 3.
- Поскольку источник не из чанков документа, source_chunk_id всегда должен быть null.
- Не добавляй markdown, комментарии или пояснения вне JSON.

FAQ-записи:
{faq_context}
"""

    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        quiz = _extract_json_array(getattr(response, "text", ""))
        if not quiz:
            print("[Ошибка] Нейросеть вернула пустой или некорректный JSON для FAQ.")
            return []
        quiz = _normalize_quiz(quiz)
        for item in quiz:
            item["source_chunk_id"] = None
        return quiz
    except Exception as e:
        print(f"[Ошибка] Нейросеть не смогла создать FAQ-квиз: {e}")
        return []

def process_document(file_path: str, num_questions: int = 5) -> dict:
    text = load_document(file_path)
    if not text:
        return {"chunks": [], "quiz": []}

    chunks = chunk_text(text)
    combined_text = ""
    for c in chunks:
        combined_text += f"[ID:{c['id']}]\n{c['text']}\n\n"

    print("-> Документ прочитан. Генерирую вопросы...")
    quiz = generate_quiz(combined_text, num_questions)

    return {"chunks": chunks, "quiz": quiz}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Путь к файлу")
    parser.add_argument("--output_dir", default="quiz_result", help="Папка вывода")
    parser.add_argument("--num_questions", type=int, default=5, help="Количество вопросов")
    args = parser.parse_args()

    print("\n" + "=" * 40)
    print(f"[*] ЗАГРУЗКА ДОКУМЕНТА: {os.path.basename(args.input)}")
    print("=" * 40)

    os.makedirs(args.output_dir, exist_ok=True)

    result = process_document(args.input, num_questions=args.num_questions)

    if result["chunks"]:
        chunks_file = os.path.join(args.output_dir, "chunks.jsonl")
        save_chunks(result["chunks"], chunks_file)
        print(f"[+] Чанки сохранены в: {chunks_file}")

    if result["quiz"]:
        output_file = os.path.join(args.output_dir, "quiz.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result["quiz"], f, ensure_ascii=False, indent=2)
        print(f"[+] ГОТОВО! Квиз сохранен в: {output_file}")
    else:
        print("[!] ОБРАБОТКА ПРЕРВАНА: Квиз не был создан (проверьте ошибки выше).")

    print("=" * 40 + "\n")

if __name__ == "__main__":
    main()
