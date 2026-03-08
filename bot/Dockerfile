FROM python:3.11-slim

LABEL maintainer="samuelc595"
LABEL description="Capitán Coditos – Discord Bot"

WORKDIR /app

RUN groupadd -r botuser && useradd -r -g botuser botuser

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R botuser:botuser /app
USER botuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "bot.py"]
