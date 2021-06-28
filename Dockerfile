FROM python:3.9.5-slim-buster AS build
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential zlib1g-dev libjpeg62-turbo-dev libfreetype6-dev
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.9.5-slim-buster
WORKDIR /app
RUN apt-get update && apt-get install -y zlib1g libjpeg62-turbo libfreetype6 && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY mathbot .
CMD ["python", "entrypoint.py", "parameters.json"]
