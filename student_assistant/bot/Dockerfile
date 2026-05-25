FROM python:3.11-slim

# ffmpeg — для конвертации webm→wav; git — для torch.hub (Silero)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# VARIANT=full ставит ML (torch/whisper/e5); VARIANT=light — только лёгкие зависимости.
ARG VARIANT=full
COPY requirements-base.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements-base.txt \
    && if [ "$VARIANT" = "full" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi

COPY . .

EXPOSE 8000

CMD ["uvicorn", "voice_server:app", "--host", "0.0.0.0", "--port", "8000"]
