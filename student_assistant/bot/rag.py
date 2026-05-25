"""Семантический поиск по корпусу (эмбеддинги).
Используется и сборщиком индекса (build_corpus.py), и рантаймом (voice_server.py).
Модель — sentence-transformers multilingual-e5; косинус по нормализованным векторам."""
import os

import numpy as np

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

_model = None


def get_model(name: str | None = None):
    """Ленивая загрузка модели эмбеддингов (кэш HF в /root/.cache)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(name or EMBEDDING_MODEL)
    return _model


def embed_passages(texts: list[str]) -> np.ndarray:
    """Эмбеддинги документов (e5 требует префикс 'passage:'). Нормализованные float32."""
    model = get_model()
    vecs = model.encode(
        [f"passage: {t}" for t in texts],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vecs.astype("float32")


def embed_query(text: str) -> np.ndarray:
    """Эмбеддинг запроса (e5 требует префикс 'query:'). Нормализованный float32."""
    model = get_model()
    vec = model.encode(
        f"query: {text}",
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vec.astype("float32")


def save_corpus(path: str, vectors: np.ndarray, meta: list[dict]) -> None:
    """Сохраняет индекс: матрица векторов + параллельный список метаданных."""
    np.savez(path, vectors=vectors.astype("float32"), meta=np.array(meta, dtype=object))


class Corpus:
    """In-memory индекс: нормализованные векторы + метаданные {tag,title,url,text}."""

    def __init__(self, vectors: np.ndarray, meta: list[dict]):
        self.vectors = vectors
        self.meta = meta

    @classmethod
    def load(cls, path: str) -> "Corpus":
        data = np.load(path, allow_pickle=True)
        return cls(data["vectors"].astype("float32"), list(data["meta"]))

    def __len__(self) -> int:
        return len(self.meta)

    def search(self, query_vec: np.ndarray, top_k: int = 5, min_score: float = 0.0) -> list[dict]:
        """Топ-k по косинусу (векторы нормализованы → скалярное произведение)."""
        if len(self.meta) == 0:
            return []
        sims = self.vectors @ query_vec
        order = np.argsort(-sims)[:top_k]
        results: list[dict] = []
        for i in order:
            score = float(sims[int(i)])
            if score < min_score:
                continue
            item = dict(self.meta[int(i)])
            item["score"] = score
            results.append(item)
        return results
