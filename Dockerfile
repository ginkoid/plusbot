FROM python:3.6.9-slim-buster

ADD . /app

WORKDIR /app/mathbot

RUN apt update && apt install build-essential git -y && pip install pipenv && pipenv install

CMD ["pipenv", "run", "python", "/app/mathbot/entrypoint.py", "parameters.json"]
