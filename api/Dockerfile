FROM python:3.11-slim

LABEL maintainer="samuelc595"
LABEL description="Capitán Coditos – Flask API"

WORKDIR /app

RUN groupadd -r apiuser && useradd -r -g apiuser apiuser

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R apiuser:apiuser /app
USER apiuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/db/stats')"

EXPOSE 5000

CMD ["gunicorn", "--workers=2", "--bind=0.0.0.0:5000", "--timeout=300", "app:create_app()"]
