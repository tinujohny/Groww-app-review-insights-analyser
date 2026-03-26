FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install project first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

# Runtime dirs used by pipeline artifacts.
RUN mkdir -p /app/data/phase7 /app/data/phase6 /app/data/phase5 /app/data/phase4 /app/data/phase2 /app/data/phase1

EXPOSE 8000

# review-pulse-api reads PORT/HOST from env.
CMD ["review-pulse-api"]
