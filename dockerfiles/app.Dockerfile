# syntax=docker/dockerfile:1
FROM python:3.12-alpine
EXPOSE 8000 8443
WORKDIR /app

# Set Timezone
ENV TZ=Asia/Seoul
RUN <<EOF
  set -eux;
  apk add --no-cache tzdata;
EOF

COPY ./requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip <<EOF
  set -eux;

  # Add `testing` Package Repository
  echo "https://dl-cdn.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories;
  apk update;

  # Install System Dependencies
  apk add --no-cache --virtual .build-deps gcc libc-dev libffi-dev;
  apk add --no-cache --virtual .mkcert-deps nss-tools mkcert;

  # Install Local CA
  mkcert -install;
  mkcert localhost 127.0.0.1 ::1;

  # Install Python Dependencies
  PYTHONDONTWRITEBYTECODE=1 pip install --no-cache-dir -r requirements.lock;

  apk del --no-network .build-deps .mkcert-deps;
EOF

COPY . .
