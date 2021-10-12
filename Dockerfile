FROM python:3.10.0-slim-bullseye AS build
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential zlib1g-dev libjpeg62-turbo-dev libfreetype6-dev
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.10.0-slim-bullseye
WORKDIR /app
RUN apt-get update && apt-get install -y zlib1g libjpeg62-turbo libfreetype6 && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY mathbot .
CMD ["python", "entrypoint.py", "parameters.json"]
