# syntax=docker/dockerfile:1
FROM --platform=arm64 python:3.12-alpine
EXPOSE 8000
WORKDIR /app

COPY ./requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip \
  pip install -r requirements.lock
