# syntax=docker/dockerfile:1
FROM python:3.10-alpine
WORKDIR /code
COPY requirements.txt requirements.txt
RUN apk add --no-cache gcc musl-dev linux-headers \
    && pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "run.py"]
