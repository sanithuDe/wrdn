FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc \
       g++ \
       unixodbc \
       unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY wrdn/backend/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY wrdn /app/wrdn

EXPOSE 8000

CMD ["uvicorn", "wrdn.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]