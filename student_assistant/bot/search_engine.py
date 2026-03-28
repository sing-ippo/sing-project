import uuid

NO_ANSWER_TEXT = 'Не знаю, попробуй переформулировать'

async def search(query: str, faq_data: list[dict], top_n: int=3) -> list[dict]:
    results = []
    score = 0
    answer = NO_ANSWER_TEXT
    for option in faq_data:
        matches = [i for i in option['keywords'] if i in query.split()]
        score = 4 * len(matches)
        if matches:
            answer = option['answer']
            results.append({"id": str(uuid.uuid4()), "query": query, "answer": answer, "score": score})
    if results:
        return results[:top_n]
    return [{"id": str(uuid.uuid4()), "query": query, "answer": answer, "score": 0}]