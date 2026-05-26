# VARIANT=light: только pandoc+regex (docx/tex/md/html), без torch/pix2text — влезает на 1 ГБ.
# VARIANT=full: + pix2text (OCR PDF/изображений, ~2 ГБ моделей).
ARG VARIANT=full
FROM python:3.11-slim
ARG VARIANT
RUN apt-get update && apt-get install -y pandoc \
    && if [ "$VARIANT" = "full" ]; then apt-get install -y libgl1 libglib2.0-0; fi \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-base.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements-base.txt \
    && if [ "$VARIANT" = "full" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi
COPY . .
CMD ["uvicorn", "formulas_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
