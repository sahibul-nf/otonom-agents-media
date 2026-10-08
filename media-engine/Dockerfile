FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (FFmpeg, sqlite3, curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements-explainer.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV MEDIA_ENGINE_PORT=8765

EXPOSE 8765

CMD ["python3", "-m", "media_engine.review_server"]
