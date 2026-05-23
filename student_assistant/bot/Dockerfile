FROM python:3.11-slim

# ffmpeg — для конвертации webm→wav; git — для torch.hub (Silero)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "voice_server:app", "--host", "0.0.0.0", "--port", "8000"]
