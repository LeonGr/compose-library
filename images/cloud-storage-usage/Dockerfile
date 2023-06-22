FROM python:3.11-slim-bullseye

WORKDIR /app

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt
RUN apt update && apt install -y curl libxml2-utils && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 9393

CMD ["python", "server.py"]
