FROM python:3.9.0-slim-buster AS build

WORKDIR /app
COPY requirements.txt .

RUN apt update && apt install build-essential zlib1g-dev libjpeg62-turbo-dev libfreetype6-dev -y && pip install -r requirements.txt

FROM python:3.9.0-slim-buster

RUN apt update && apt install zlib1g-dev libjpeg62-turbo libfreetype6 -y && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY . /app

WORKDIR /app/mathbot
CMD ["python", "-u", "entrypoint.py", "parameters.json"]
