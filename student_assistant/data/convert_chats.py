import json
import re
from pathlib import Path
from datetime import datetime
from collections import Counter
from functools import lru_cache

from pymorphy3 import MorphAnalyzer


# ================== CONFIG ==================

BASE_DIR = Path(__file__).resolve().parent
SOURCES_DIR = BASE_DIR / "sources"

CHAT_PATH = SOURCES_DIR / "student_questions.json"
OUTPUT_PATH = BASE_DIR / "faq_chats.json"
REJECTED_PATH = BASE_DIR / "rejected_chats.json"

DEFAULT_SOURCE = "chat_подслушано_мирэа"

START_ID = 2000

MIN_QUESTION_LENGTH = 12
MAX_QUESTION_LENGTH = 450

MIN_KEYWORD_LENGTH = 3
MAX_KEYWORDS = 10

DEFAULT_ANSWER = "Ответ будет добавлен после модерации."

WORD_RE = re.compile(r"[a-zа-яё]+", re.IGNORECASE)

morph = MorphAnalyzer()


# ================== FILTER CONFIG ==================

STOP_MESSAGES = {
    "ок",
    "окей",
    "спасибо",
    "спс",
    "понял",
    "поняла",
    "да",
    "нет",
    "+",
    "-",
}

KEYWORD_STOP_WORDS = {
    "и", "в", "во", "на", "по", "с", "со", "к", "ко",
    "а", "но", "или", "это", "как", "что", "для",
    "из", "от", "до", "при", "об", "о", "у", "за",
    "есть", "быть", "также", "можно", "нужно",
    "какой", "какая", "какие", "какого", "какую",
    "когда", "где", "куда", "почему", "зачем",
    "сколько", "чем", "кто", "ли", "мне", "нам",
    "тебе", "вам", "они", "оно", "она", "он",
    "мы", "вы", "я", "ты", "же", "бы", "то",
    "вот", "там", "тут", "тоже", "уже", "еще", "ещё",
    "просто", "вообще", "типа", "типо", "всем", "привет",
    "подскажите", "пожалуйста", "ребята", "ребят",
    "человек", "люди", "который", "которая", "которые",
    "чтобы", "если", "весь", "все", "всё",
}

STOP_WORDS = set(STOP_MESSAGES) | set(KEYWORD_STOP_WORDS)

ALLOWED_SHORT_WORDS = {
    "егэ",
    "сдо",
    "лк",
    "git",
    "sql",
    "dml",
    "if",
    "брс",
    "спо",
    "вуз",
}

BAD_PHRASES = {
    # Посты / цитаты / реклама
    "прислать пост",
    "все цитаты",
    "все цитаты прислать пост",
    "анонимно пожалуйста",
    "с уважением",
    "доброго времени суток",
    "всем приветики",
    "тьмоки чпоки",
    "тьмоки чпоки мирэа",

    "регистрируйтесь по ссылке",
    "получите бесплатный доступ",
    "подробнее о конкурсе",
    "призовой фонд",
    "к участию приглашаются",
    "официальном сайте",
    "онлайн помощь",
    "заказчики создают задачи",
    "исполнители отправляют отклики",
    "скачайте приложение",
    "подписывайтесь на канал",
    "переходите по ссылке",
    "оставить отзыв",
    "до конца года",

    # Флуд / мемы / явно не FAQ
    "демоверсия фанфика",
    "нормальные люди так не делают",
    "идем пить водку",
    "идём пить водку",
    "так мы идем пить водку",
    "так мы идём пить водку",
    "пойти на практику бухие",
    "ходили на практику не бухие",
    "курить вейп",
    "играть в пасьянс",
    "все завтра в вуз можете не идти",
    "начинать курить",
    "энергетики это вредно",
    "нахуя препода съели",
    "ссылка на потеряшки",

    # Агрессия / драки
    "выйдешь на улицу",
    "в лицо мне скажешь",
    "идём на штурм",
    "идем на штурм",
    "устроим массовую сходку",
    "файт будет",
    "набивке силы",
}

BAD_WORD_PARTS = {
    # Мат / обсценная лексика
    "хуй",
    "хуя",
    "хуе",
    "хуё",
    "хуйн",
    "поху",
    "ниху",

    "пизд",
    "пизж",

    "ёб",
    "уёб",
    "уеб",
    "заёб",
    "заеб",
    "проёб",
    "проеб",
    "наёб",
    "наеб",
    "выёб",
    "выеб",
    "разъёб",
    "разъеб",
    "отъёб",
    "отъеб",
    "доёб",
    "доеб",
    "еблан",
    "ебуч",

    "бля",
    "бляд",
    "блять",

    # Оскорбления
    "мудак",
    "мудил",
    "мудоз",
    "мраз",
    "гнид",
    "сучар",
    "сучк",
    "долба",
    "долбо",
    "дебил",
    "идиот",
    "кретин",
    "шлюх",
    "шалав",
    "мразот",

    # Грубые / сексуальные / телесные
    "дроч",
    "конч",
    "сперм",
    "сиськ",
    "порн",
    "трах",
    "изнас",
    "домог",

    # Алкоголь / курение / наркотики / азарт
    "водк",
    "бух",
    "бухат",
    "бухой",
    "алкаш",
    "алког",
    "сигар",
    "вейп",
    "наркот",
    "спайс",
    "казик",
    "казино",
    "дурак",
    "покер",

    # Мемный мусор
    "фанфик",
    "стонал",
    "фурри",
    "тьмоки",
    "чпоки",

    # списывание / шпаргалки
    "списать",
    "списывать",
    "списыв",
    "шпор",
    "шпаргал",

    # грубый / неуместный оффтоп
    "морг",
    "похав",
    "презик",
    "курилк",

    # мемный мусор
    "мем",
    "рофл",
    "рофлить",
}

BAD_EXACT_WORDS = {
    "ебать",
    "ебут",
    "ебали",
    "ебаный",
    "ебаная",
    "ебаное",
    "ебаные",
    "еблан",
    "ебланы",
    "сука",
    "сучка",
    "хер",
    "хрен",
    "говно",
    "говна",
    "дерьмо",
    "жопа",
    "жопу",
    "очко",
    "секс",
    "анал",
    "член",
    "пиво",
    "водка",
    "вейп",
    "трап",
}

BAD_WORD_EXCEPTIONS = {
    # Чтобы фильтр не выкидывал нормальные учебные слова
    "учеба",
    "учебный",
    "учебное",
    "учебные",
    "учебного",
    "учебном",
    "матанализ",
    "матанал",
    "канал",
    "анализ",
    "анализу",
    "анализом",
}

STUDY_MARKERS = {
    # Экзамены / учебный процесс
    "экзамен",
    "экзамены",
    "зачет",
    "зачёт",
    "сессия",
    "пересдача",
    "долг",
    "долги",
    "балл",
    "баллы",
    "брс",
    "автомат",
    "допуск",
    "оценка",
    "тройка",
    "контрольная",
    "лаба",
    "лабораторная",
    "курсовая",
    "практика",
    "семестр",
    "курс",
    "пара",
    "пары",
    "лекция",
    "занятие",
    "посещение",
    "консультация",
    "зачетка",
    "зачётка",
    "физра",
    "физре",
    "физру",
    "физкультура",
    "физкультуре",
    "фок",
    "норматив",
    "нормативы",
    "бассейн",
    "спортзал",
    "зал",
    "спецгруппа",
    "специальная группа",

    # Навигация
    "расписание",
    "корпус",
    "аудитория",
    "кабинет",
    "адрес",
    "стромынка",
    "вернадского",

    # Общежитие
    "общежитие",
    "общага",
    "заселение",

    # IT-системы
    "сдо",
    "лк",
    "личный кабинет",
    "почта",
    "аккаунт",
    "пароль",
    "логин",
    "moodle",

    # Преподаватели
    "препод",
    "преподаватель",
    "лектор",
    "семинарист",
    "куратор",

    # Бюрократия
    "деканат",
    "учебный отдел",
    "справка",
    "заявление",
    "документ",
    "приказ",
    "паспорт",
    "пропуск",

    # Стипендия
    "стипендия",
    "стипуха",
    "социальная стипендия",
    "соц стипендия",
    "выплата",
    "выплаты",
    "дотация",
    "дотации",

    # ВУЦ
    "вуц",
    "военка",
    "военная кафедра",
    "военкомат",
    "отсрочка",
    "преписное",
    "сержант",
    "офицер",
    "солдат",
    "сборы",

    # Поступление / перевод
    "поступление",
    "поступить",
    "егэ",
    "бюджет",
    "платка",
    "платное",
    "платный",
    "перевестись",
    "перевод",
    "направление",
    "магистратура",
    "бакалавриат",
    "спо",
    "колледж",
    "абитуриент",

    # ДОД / приёмная кампания
    "день открытых дверей",
    "дод",
    "абитуриенты",
    "поступающий",
    "поступающие",
    "прием",
    "приём",
    "приемная комиссия",
    "приёмная комиссия",
    "приемная кампания",
    "приёмная кампания",
    "правила приема",
    "правила приёма",
    "подать документы",
    "подача документов",
    "сроки подачи",
    "документы для поступления",

    # Документы
    "аттестат",
    "диплом",
    "снилс",
    "оригинал",
    "копия",
    "документ об образовании",
    "согласие на зачисление",
    "зачисление",
    "приказ о зачислении",

    # Экзамены / поступление
    "вступительные испытания",
    "вступительные",
    "испытания",
    "предметы",
    "профильная математика",
    "русский язык",
    "информатика",
    "физика",
    "химия",
    "биология",
    "обществознание",
    "история",
    "иностранный язык",

    # Конкурс / баллы
    "конкурс",
    "конкурсные списки",
    "списки поступающих",
    "рейтинговые списки",
    "рейтинг",
    "проходной балл",
    "проходные баллы",
    "конкурсный балл",
    "сумма баллов",
    "минимальные баллы",
    "минимальный балл",
    "индивидуальные достижения",
    "дополнительные баллы",

    # Места / формы обучения
    "бюджетные места",
    "места",
    "контрольные цифры приема",
    "контрольные цифры приёма",
    "кцп",
    "договор",
    "договорное обучение",
    "платное обучение",
    "стоимость обучения",
    "очная форма",
    "очно-заочная форма",
    "заочная форма",

    # Уровни образования
    "бакалавр",
    "специалитет",
    "магистр",
    "аспирантура",
    "после колледжа",

    # Особые условия
    "целевое обучение",
    "целевое",
    "целевая квота",
    "квота",
    "особая квота",
    "отдельная квота",
    "льготы",
    "олимпиада",
    "олимпиады",
    "бви",
    "без вступительных испытаний",

    # Общежитие для поступающих
    "иногородний",
    "иногородние",
    "место в общежитии",
    "общежитие для поступающих",
}


# ================== CATEGORY CONFIG ==================

CATEGORY_PRIORITY = [
    "поступление",
    "экзамены",
    "общежитие",
    "ит_системы",
    "бюрократия",
    "навигация",
    "преподаватели",
    "учебный_процесс",
]

RAW_CATEGORY_KEYWORDS = {
    "поступление": {
        "егэ",
        "проходной",
        "поступить",
        "поступление",
        "поступать",
        "абитуриент",
        "бюджет",
        "бюджетный",
        "платное",
        "платный",
        "прием",
        "приём",
        "приемная",
        "приёмная",
        "направление",
        "направления",
        "зачисление",
        "конкурс",
        "спо",
        "колледж",
        "магистратура",
        "бакалавриат",
        "вступительный",
    },
    "экзамены": {
        "экзамен",
        "экзамены",
        "зачет",
        "зачёт",
        "сессия",
        "пересдача",
        "пересдать",
        "долг",
        "долги",
        "аттестация",
        "контрольная",
        "оценка",
        "тройка",
        "автомат",
        "допуск",
        "брс",
        "балл",
        "баллы",
    },
    "общежитие": {
        "общежитие",
        "общага",
        "заселение",
        "комната",
        "иногородний",
        "проживание",
    },
    "ит_системы": {
        "лк",
        "сдо",
        "аккаунт",
        "почта",
        "логин",
        "пароль",
        "moodle",
        "сайт",
        "личный",
        "кабинет",
    },
    "бюрократия": {
        "справка",
        "заявление",
        "деканат",
        "приказ",
        "подпись",
        "печать",
        "документ",
        "документы",
        "паспорт",
        "учебный",
        "отдел",
    },
    "навигация": {
        "расписание",
        "корпус",
        "аудитория",
        "кабинет",
        "адрес",
        "найти",
        "находиться",
        "карта",
    },
    "преподаватели": {
        "преподаватель",
        "лектор",
        "семинарист",
        "препод",
        "куратор",
    },
}

CATEGORY_PHRASES = {
    "поступление": {
        "проходной балл",
        "проходные баллы",
        "баллы егэ",
        "баллы для поступления",
        "баллы при поступлении",
        "бюджетные места",
        "приемная комиссия",
        "приёмная комиссия",
        "документы для поступления",
        "подать документы",
        "после колледжа",
        "после спо",
    },
    "экзамены": {
        "баллы за семестр",
        "баллы в брс",
        "баллов в брс",
        "добрать баллы",
        "получить баллы",
        "не хватает баллов",
        "пересдача экзамена",
        "сдать экзамен",
        "сдать зачет",
        "сдать зачёт",
    },
    "общежитие": {
        "место в общежитии",
        "дают общежитие",
        "дают общагу",
    },
    "ит_системы": {
        "личный кабинет",
        "электронная почта",
    },
    "навигация": {
        "как найти",
        "где находится",
        "в каком корпусе",
    },
}


# ================== UTILS ==================

def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


def load_json(path: str | Path) -> list:
    path = Path(path)

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            log(f"Ошибка: файл {path} должен содержать список")
            return []

        return data

    except FileNotFoundError:
        log(f"Предупреждение: файл не найден: {path}")
        return []

    except json.JSONDecodeError:
        log(f"Ошибка: файл {path} содержит некорректный JSON")
        return []


def save_json(data: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    text = text.replace("\n", " ").replace("\t", " ")
    text = text.replace("\r", " ").replace("\xa0", " ")
    text = " ".join(text.split())

    return text.strip()


def normalize_for_filter(text: str) -> str:
    if not isinstance(text, str):
        return ""

    return clean_text(text).lower().replace("ё", "е")


# ================== FILTERING ==================

def has_bad_phrase(text: str) -> bool:
    text = normalize_for_filter(text)

    for phrase in BAD_PHRASES:
        normalized_phrase = phrase.lower().replace("ё", "е")

        if normalized_phrase in text:
            return True

    return False


def has_bad_words(text: str) -> bool:
    text = normalize_for_filter(text)
    words = WORD_RE.findall(text)

    for word in words:
        if word in BAD_WORD_EXCEPTIONS:
            continue

        if word in BAD_EXACT_WORDS:
            return True

        for bad_part in BAD_WORD_PARTS:
            if bad_part in word:
                return True

    return False


def normalize_word(word: str) -> str:
    return morph.parse(word)[0].normal_form


NORMALIZED_STUDY_MARKERS = {
    normalize_word(marker)
    for marker in STUDY_MARKERS
    if " " not in marker
}


def has_study_marker(text: str) -> bool:
    if not text:
        return False

    normalized_text = clean_text(text).lower()

    for marker in STUDY_MARKERS:
        marker = marker.lower().strip()

        if " " in marker and marker in normalized_text:
            return True

    words = re.findall(r"[а-яёa-z0-9]+", normalized_text)
    normalized_words = {normalize_word(word) for word in words}

    return bool(normalized_words & NORMALIZED_STUDY_MARKERS)

def has_question_meaning(text: str) -> bool:
    text = normalize_for_filter(text)

    if "?" in text:
        return True

    question_words = (
        "как",
        "где",
        "когда",
        "куда",
        "зачем",
        "почему",
        "какой",
        "какая",
        "какие",
        "сколько",
        "можно ли",
        "что",
        "кто",
        "чем",
        "для чего",
    )

    return any(word in text for word in question_words)


def get_reject_reason(text: str) -> str | None:
    text = clean_text(text)
    lower_text = text.lower()

    if not text:
        return "empty"

    if lower_text in STOP_MESSAGES:
        return "stop_message"

    if len(text) < MIN_QUESTION_LENGTH:
        return "too_short"

    if len(text) > MAX_QUESTION_LENGTH:
        return "too_long"

    if not re.search(r"[а-яёa-z]", lower_text, re.IGNORECASE):
        return "no_letters"

    if has_bad_phrase(text):
        return "bad_phrase"

    if has_bad_words(text):
        return "bad_words"

    if not has_question_meaning(text):
        return "no_question_meaning"

    if not has_study_marker(text):
        return "no_study_marker"

    return None


def is_useful_question(text: str) -> bool:
    return get_reject_reason(text) is None


# ================== KEYWORDS ==================

def extract_keywords(text: str, max_keywords: int = MAX_KEYWORDS) -> list[str]:
    """
    Создаёт keywords из текста вопроса без лемматизации.
    Лемматизация keywords выполняется позже в build_faq.py.
    """
    if not isinstance(text, str):
        return []

    words = WORD_RE.findall(text.lower().replace("ё", "е"))

    keywords = []
    seen = set()

    for word in words:
        if len(word) < MIN_KEYWORD_LENGTH and word not in ALLOWED_SHORT_WORDS:
            continue

        if word in STOP_WORDS:
            continue

        if word in seen:
            continue

        keywords.append(word)
        seen.add(word)

        if len(keywords) >= max_keywords:
            break

    return keywords


# ================== LEMMATIZATION FOR CATEGORY ==================

@lru_cache(maxsize=10000)
def normalize_word(word: str) -> str:
    word = word.lower().replace("ё", "е")
    return morph.parse(word)[0].normal_form


def get_lemmas(text: str) -> set[str]:
    if not isinstance(text, str):
        return set()

    text = text.lower().replace("ё", "е")
    words = WORD_RE.findall(text)

    lemmas = set()

    for word in words:
        lemmas.add(normalize_word(word))

    return lemmas


def build_category_keywords() -> dict[str, set[str]]:
    normalized_categories = {}

    for category, keywords in RAW_CATEGORY_KEYWORDS.items():
        normalized_words = set()

        for keyword in keywords:
            normalized_words.update(get_lemmas(keyword))

        normalized_categories[category] = normalized_words

    return normalized_categories


CATEGORY_KEYWORDS = build_category_keywords()


# ================== CATEGORY DETECTION ==================

def detect_category(question: str, source: str = "") -> str:
    if not isinstance(question, str):
        return "учебный_процесс"

    question_lower = question.lower().replace("ё", "е")
    question_lemmas = get_lemmas(question)

    scores = {category: 0 for category in CATEGORY_PRIORITY}

    for category, phrases in CATEGORY_PHRASES.items():
        for phrase in phrases:
            normalized_phrase = phrase.lower().replace("ё", "е")

            if normalized_phrase in question_lower:
                scores[category] += 3

    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = question_lemmas & keywords
        scores[category] += len(matches)

    if source == "chat_поступление_иит":
        scores["поступление"] += 1

    if source == "chat_экзамены_мирэа":
        scores["экзамены"] += 1

    best_category = "учебный_процесс"
    best_score = 0

    for category in CATEGORY_PRIORITY:
        score = scores.get(category, 0)

        if score > best_score:
            best_score = score
            best_category = category

    if best_score == 0:
        return "учебный_процесс"

    return best_category


# ================== CHAT PROCESSING ==================

def extract_message_text(raw_item) -> str:
    if isinstance(raw_item, str):
        return clean_text(raw_item)

    if not isinstance(raw_item, dict):
        return ""

    for field in ("question", "text", "message", "content", "body"):
        value = raw_item.get(field)

        if isinstance(value, str):
            return clean_text(value)

    return ""


def extract_message_source(raw_item, default_source: str = DEFAULT_SOURCE) -> str:
    if isinstance(raw_item, dict):
        source = raw_item.get("source")

        if isinstance(source, str) and source.strip():
            return clean_text(source)

    return default_source


def normalize_question_for_grouping(question: str) -> str:
    question = question.lower().replace("ё", "е")
    question = re.sub(r"[^\w\sа-яё]", " ", question, flags=re.IGNORECASE)
    question = " ".join(question.split())

    return question


def load_chat_messages(
    chat_path: str | Path = CHAT_PATH,
    default_source: str = DEFAULT_SOURCE,
) -> list[dict]:
    raw_items = load_json(chat_path)
    messages = []

    for raw_item in raw_items:
        question = extract_message_text(raw_item)

        if not question:
            continue

        source = extract_message_source(raw_item, default_source)

        messages.append({
            "question": question,
            "source": source,
        })

    return messages


def group_similar_questions(messages: list[dict]) -> tuple[list[dict], list[dict], dict]:
    grouped = {}
    frequency = Counter()
    rejected = []

    stats = {
        "total_messages": len(messages),
        "accepted_questions": 0,
        "rejected_messages": 0,
        "grouped_questions": 0,
        "reject_reasons": Counter(),
    }

    for message in messages:
        question = clean_text(message.get("question", ""))
        source = message.get("source", DEFAULT_SOURCE)

        reject_reason = get_reject_reason(question)

        if reject_reason:
            stats["rejected_messages"] += 1
            stats["reject_reasons"][reject_reason] += 1

            rejected.append({
                "question": question,
                "source": source,
                "reason": reject_reason,
            })

            continue

        stats["accepted_questions"] += 1

        normalized_question = normalize_question_for_grouping(question)
        group_key = (normalized_question, source)

        frequency[group_key] += 1

        if group_key not in grouped:
            grouped[group_key] = {
                "question": question,
                "source": source,
            }

    result = []

    for group_key, data in grouped.items():
        data["frequency"] = frequency[group_key]
        result.append(data)

    stats["grouped_questions"] = len(result)
    stats["reject_reasons"] = dict(stats["reject_reasons"])

    return result, rejected, stats


def make_answer(frequency: int) -> str:
    if frequency > 1:
        return f"{DEFAULT_ANSWER} Вопрос встречался в чатах {frequency} раз."

    return DEFAULT_ANSWER


def convert_question_to_faq_entry(question_data: dict, index: int) -> dict:
    question = clean_text(question_data.get("question", ""))
    source = question_data.get("source", DEFAULT_SOURCE)
    frequency = question_data.get("frequency", 1)

    keywords = extract_keywords(question)
    category = detect_category(question, source)
    answer = make_answer(frequency)

    return {
        "id": START_ID + index,
        "question": question,
        "keywords": keywords,
        "answer": answer,
        "category": category,
        "source": source,
    }


def convert_all_chat_questions(messages: list[dict]) -> tuple[list[dict], list[dict], dict]:
    grouped_questions, rejected, stats = group_similar_questions(messages)

    entries = []

    for question_data in grouped_questions:
        entry = convert_question_to_faq_entry(
            question_data=question_data,
            index=len(entries),
        )

        entries.append(entry)

    stats["faq_entries"] = len(entries)

    return entries, rejected, stats


def convert_chats(
    chat_path: str | Path = CHAT_PATH,
    output_path: str | Path = OUTPUT_PATH,
    rejected_path: str | Path = REJECTED_PATH,
    default_source: str = DEFAULT_SOURCE,
) -> list[dict]:
    messages = load_chat_messages(
        chat_path=chat_path,
        default_source=default_source,
    )

    if not messages:
        log("Предупреждение: сообщения из чатов не найдены")

    entries, rejected, stats = convert_all_chat_questions(messages)

    save_json(entries, output_path)
    save_json(rejected, rejected_path)

    log(f"Загружено сообщений: {stats['total_messages']}")
    log(f"Принято вопросов: {stats['accepted_questions']}")
    log(f"Отклонено сообщений: {stats['rejected_messages']}")
    log(f"После группировки: {stats['grouped_questions']}")
    log(f"Сохранено FAQ-записей: {stats['faq_entries']}")
    log(f"Отклонённые сохранены: {rejected_path}")

    reject_reasons = stats.get("reject_reasons", {})

    if reject_reasons:
        log("Причины отклонения:")

        for reason, count in reject_reasons.items():
            log(f"  {reason}: {count}")

    log(f"Файл сохранён: {output_path}")

    return entries


def main() -> None:
    convert_chats(
        chat_path=CHAT_PATH,
        output_path=OUTPUT_PATH,
        rejected_path=REJECTED_PATH,
        default_source=DEFAULT_SOURCE,
    )


if __name__ == "__main__":
    main()
