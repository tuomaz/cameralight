FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get install python3-opencv -y

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
