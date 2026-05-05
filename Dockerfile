# syntax=docker/dockerfile:1
FROM python:3.10-alpine

WORKDIR /code

COPY requirements.txt requirements.txt

RUN apk add --no-cache gcc musl-dev linux-headers \
    && pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:8080"]