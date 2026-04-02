import argparse
import json
import os
import sys
from dotenv import load_dotenv
load_dotenv()
def load_txt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
def load_pdf(path):
    try:
        import PyPDF2
    except ImportError:
        print("Необходимо установть PyPDF2: pip install PyPDF2")
        sys.exit(1)
    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text
def load_docx(path):
    try:
        import docx
    except ImportError:
        print("Необходимо установть python-docx: pip install python-docx")
        sys.exit(1)
    doc = docx.Document(path)
    return "\n".join([p.text for p in doc.paragraphs])
def load_document(path):
    if not os.path.exists(path):
        print(f"Файл не найден: {path}")
        sys.exit(1)
    max_size = 50 * 1024  # 50 KB
    file_size = os.path.getsize(path)
    if file_size > max_size:
        print(f"Файл слишком большой ({file_size} байт). Максимум — 50 KB")
        sys.exit(1)
    if not (path.endswith(".txt") or path.endswith(".pdf") or path.endswith(".docx")):
        print("Неподдерживаемый формат файла. Используй .txt, .pdf или .docx")
        sys.exit(1)
    if path.endswith(".txt"):
        text = load_txt(path)
    elif path.endswith(".pdf"):
        text = load_pdf(path)
    elif path.endswith(".docx"):
        text = load_docx(path)
    if not text or not text.strip():
        print("Файл пустой или не содержит текста")
        sys.exit(1)
    return text

def chunk_text(text, chunk_size=400, overlap=50):
    words = text.split()
    chunks = []
    start = 0
    chunk_id = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append({
            "id": chunk_id,
            "text": " ".join(chunk_words)
        })
        start += chunk_size - overlap
        chunk_id += 1
    return chunks

def save_chunks(chunks, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

def generate_quiz(text, num_questions=5):
    try:
        from google import genai
    except ImportError:
        print("Необходимо установить библиотеку: pip install google-generativeai")
        return []

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY не найден")
        return []

    client = genai.Client(api_key=api_key)

    prompt = f"""
Создай {num_questions} вопросов с множественным выбором.

Формат JSON:
[
  {{
    "id": ...
    "question": "...",
    "options": ["...", "...", "...", "..."],
    "correct": 0,
    "explanation": "...",
    "source_chunk_id": 0
  }}
]

Текст:
{text}
"""

    try:
        response = client.models.generate_content(
            model='models/gemini-2.5-flash',
            contents=prompt
        )
    except Exception as e:
        print(f"Ошибка Gemini API: {e}")
        return []

    if not response.text:
        return []

    quiz_text = response.text

    start = quiz_text.find("[")
    end = quiz_text.rfind("]") + 1

    if start == -1 or end == 0:
        return []

    try:
        quiz = json.loads(quiz_text[start:end])
    except:
        return []

    for q in quiz:
        if "source_chunk_id" not in q:
            q["source_chunk_id"] = None

    return quiz

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Путь к текстовому файлу")
    parser.add_argument("--output", default="quiz.json", help="Файл для сохранения")
    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)
    chunks_path = os.path.join(args.output, "chunks.jsonl")
    quiz_path = os.path.join(args.output, "quiz.json")
    print("Загрузка документа")
    result = process_document(args.input)

    save_chunks(result["chunks"], chunks_path)

    with open(quiz_path, "w", encoding="utf-8") as f:
        json.dump(result["quiz"], f, ensure_ascii=False, indent=2)

    print(f"Готово! Результат сохранён в {args.output}")

def process_document(file_path: str, num_questions: int = 5) -> dict:
    text = load_document(file_path)
    chunks = chunk_text(text)

    combined_text = ""
    for c in chunks[:5]:
        combined_text += f"[CHUNK_ID={c['id']}]\n{c['text']}\n\n"

    quiz = generate_quiz(combined_text, num_questions)

    return {
        "chunks": chunks,
        "quiz": quiz
    }

if __name__ == "__main__":
    main()
