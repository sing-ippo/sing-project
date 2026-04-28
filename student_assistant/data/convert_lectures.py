import json
import re
import nltk as nt
from datetime import datetime
from nltk.corpus import stopwords
from pymorphy3 import MorphAnalyzer

STOP_WORDS = set(stopwords.words('russian'))
morph = MorphAnalyzer()
STOP_WORDS.update(["такое"])
STOP_WORDS.update(stopwords.words('english'))
MIN_LENGTH_WORD = 3
START_ID = 1000
WORD_PATTERN = re.compile(r'^[a-zа-яё]+(?:-[a-zа-яё]+)*$')

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def get_clean_keywords(text_list: list[str]) -> list[str]:
    if not text_list:
        return []
        
    unique_words = {} 
    
    for text in text_list:
        tokens = nt.word_tokenize(text, language="russian")
        for word in tokens:
            clean_word = word.lower()
            if len(clean_word) < MIN_LENGTH_WORD or clean_word in STOP_WORDS:
                continue
            if WORD_PATTERN.match(clean_word):
                parsed = morph.parse(clean_word)[0]
                if parsed.tag.POS == 'NPRO':
                    continue
                    
                lemma = parsed.normal_form
                if lemma not in STOP_WORDS:
                    unique_words[lemma] = None
                
    return list(unique_words.keys())

def convert_lectures(lectures_path: str, faq_path: str) -> list[dict]:
    combined_data = []
    current_id = START_ID
    
    nt.download('punkt_tab', quiet=True)
    nt.download('stopwords', quiet=True)

    try:
        with open(lectures_path, "r", encoding="UTF-8") as f:
            lectures_list = json.load(f)
            lectures_lookup = {l['id']: get_clean_keywords(l.get('key_points', [])) for l in lectures_list}
        with open(faq_path, "r", encoding="UTF-8") as f:
            faqs = json.load(f)
        
    except FileNotFoundError as e:
        log(f"Ошибка: Не найден файл {e.filename}")
        return
    
    for item in faqs:
        l_id = item.get("lecture_id")
        q_text = item.get("question")
        a_text = item.get("answer")
        
        lecture_keywords = lectures_lookup.get(l_id)
        question_keywords = get_clean_keywords([q_text])
        keywords = list(set(lecture_keywords + question_keywords))

        combined_data.append({
            "id": current_id,
            "question": q_text,     
            "keywords": keywords,     
            "answer": a_text,         
            "category": "лекции",
            "source": f"lecture_{l_id}"
        })
        current_id += 1

    with open("faq_lectures.json", "w", encoding="UTF-8") as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=4)
    return combined_data

if __name__ == "__main__":
    convert_lectures("lectures.json", "lecture_faq.json")