import re

def deduplicate(entries, threshold=85):
    """
    Двухэтапная дедупликация:
    1. Точное совпадение по тексту (O(n))
    2. Нечеткое совпадение по ключевым словам или тексту вопроса (O(k^2))
    """
    
    if not entries:
        return [], 0

    # ЭТАП 1: Быстрая очистка через хэш-таблицу
    exact_map = {}
    initial_count = len(entries)
    
    for entry in entries:
        
        q_norm = entry.get('question', '').strip().lower()
        if entry.get('category') == 'лекции':
            key = f"lect_{entry.get('id')}_{entry.get('source')}"
        else:
            key = q_norm
        if key not in exact_map:
            exact_map[key] = entry
        else:
            # Оставляем запись с более полным ответом
            if len(str(entry.get('answer', ''))) > len(str(exact_map[key].get('answer', ''))):
                exact_map[key] = entry

    pre_filtered = list(exact_map.values())
    exact_removed = initial_count - len(pre_filtered)

    # ЭТАП 2: Нечеткое сравнение
    unique = []
    fuzzy_removed = 0

    for entry in pre_filtered:
        if entry.get('category') == 'лекции':
            unique.append(entry)
            continue
        is_duplicate = False
        # Пытаемся взять keywords, если их нет — генерируем из вопроса
        kw1 = set(entry.get('keywords', []))
        if not kw1:
            kw1 = set(re.findall(r'[а-яёa-z]{2,}', entry.get('question', '').lower()))


        for i, existing in enumerate(unique):
            if existing.get('category') == 'лекции':
                continue
            kw2 = set(existing.get('keywords', []))
            if not kw2:
                kw2 = set(re.findall(r'[а-яёa-z]{2,}', existing.get('question', '').lower()))

            if not kw1 or not kw2:
                continue
            
            # Считаем сходство (Жаккар)
            common = kw1 & kw2
            max_len = max(len(kw1), len(kw2))
            similarity = (len(common) / max_len) * 100
            
            q1 = entry.get('question', '')
            q2 = existing.get('question', '')

            if similarity >= threshold:
                len_ratio = min(len(q1), len(q2)) / max(len(q1), len(q2))
            
                if len_ratio < 0.6: 
                    continue

                is_duplicate = True
                fuzzy_removed += 1
                
                curr_ans = str(entry.get('answer', '')).strip()
                exis_ans = str(existing.get('answer', '')).strip()

                if exis_ans == "None" and curr_ans != "None":
                    unique[i] = entry
                elif curr_ans != "None" and len(curr_ans) > len(exis_ans):
                    unique[i] = entry
                break
        
        if not is_duplicate:
            unique.append(entry)

    return unique, (exact_removed + fuzzy_removed)
