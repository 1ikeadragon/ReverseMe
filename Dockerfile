FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN apt update && apt install -y xxd binutils

COPY . .

CMD ["python", "main.py"]
