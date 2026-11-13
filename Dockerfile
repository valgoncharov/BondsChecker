FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Moscow \
    DB_PATH=/data/bonds.db

WORKDIR /app

COPY bond_notifier/requirements.txt ./bond_notifier/requirements.txt
RUN pip install --no-cache-dir -r bond_notifier/requirements.txt

COPY bond_notifier/ ./bond_notifier/

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data \
    && chown -R app:app /data /app

USER app

WORKDIR /app/bond_notifier

CMD ["python", "main.py"]
