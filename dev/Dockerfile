FROM python:3.13.5-alpine3.22

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache freetds-dev unixodbc-dev gcc musl-dev linux-headers postgresql-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/logs

COPY sync_script.py .

CMD ["python", "sync_script.py"]