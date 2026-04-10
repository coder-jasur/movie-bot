FROM python:3.13-slim

WORKDIR /app

# Upgrade pip and install uv
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir uv

# Install system dependencies (ffmpeg is required for worker)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy configuration files
COPY pyproject.toml /app/

# Compile requirements
RUN uv pip compile pyproject.toml > requirements.txt

# Install dependencies system-wide
RUN uv pip install -r requirements.txt --system

# Copy application code
COPY . /app/

# Compile translations
RUN pybabel compile -d translations

# Start Celery worker
CMD ["celery", "-A", "src.app.core.celery_app", "worker", "--loglevel=info"]
