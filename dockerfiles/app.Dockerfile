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

  # Install System Dependencies
  apk add --no-cache --virtual .build-deps gcc libc-dev libffi-dev;

  # Install Python Dependencies
  PYTHONDONTWRITEBYTECODE=1 pip install --no-cache-dir -r requirements.lock;

  apk del --no-network .build-deps;
EOF

COPY . .
