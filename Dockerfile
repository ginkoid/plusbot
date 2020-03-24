FROM python:3.7.5-slim-buster AS build

ADD ./requirements.txt /app/requirements.txt
WORKDIR /app

RUN apt update && apt install git build-essential -y && pip install -r /app/requirements.txt

FROM python:3.7.5-slim-buster AS run

COPY --from=build /usr/local/lib/python3.7/site-packages /usr/local/lib/python3.7/site-packages
ADD . /app

WORKDIR /app/mathbot

CMD ["python", "/app/mathbot/entrypoint.py", "parameters.json"]
