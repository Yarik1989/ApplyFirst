FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY assets ./assets

RUN mkdir -p /app/data

CMD ["python", "-m", "backend.main"]
