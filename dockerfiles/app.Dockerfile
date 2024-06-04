# syntax=docker/dockerfile:1
FROM python:3.12-alpine as base
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

# local target
FROM base as local
RUN <<EOF
  set -eux;
  apk add nodejs npm;
  npm install -g concurrently;
EOF
COPY . .

# prod target
FROM base as prod
RUN <<EOF
  set -eux;
  python manage.py tailwind build;
EOF
COPY . .
