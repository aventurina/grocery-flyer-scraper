FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

ENV CHROMIUM_NO_SANDBOX=1 \
    PYTHONUNBUFFERED=1

# One worker and one thread: the scraper runs a real browser, so keep memory use low.
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 1 --timeout 120
