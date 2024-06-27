# syntax=docker/dockerfile:1
FROM python:3.12-alpine as base
EXPOSE 8000 8443
WORKDIR /app

# Set Timezone
ENV TZ=Asia/Seoul
RUN --mount=type=cache,target=/var/cache/apk <<EOF
  set -eux;
  apk add tzdata;
EOF

RUN <<EOF
  set -eux;
  python -m venv .venv;
  source .venv/bin/activate;
EOF

COPY ./requirements.lock ./requirements.lock
RUN --mount=type=cache,target=/root/.cache/pip --mount=type=cache,target=/var/cache/apk <<EOF
  set -eux;

  # Install System Dependencies
  apk add --virtual .build-deps build-base libc-dev libffi-dev git;

  # Install Python Dependencies
  pip install -r requirements.lock;

  apk del --no-network .build-deps;

  apk add nodejs npm;
EOF

# local target
FROM base as local
RUN --mount=type=cache,target=/var/cache/apk --mount=type=cache,target=/root/.npm <<EOF
  set -eux;
  npm install -g concurrently;
EOF
COPY . .

# prod target
FROM base as prod
COPY . .
RUN <<EOF
  set -eux;
  env SECRET_KEY='noop' DB_PASSWORD='noop' DB_HOST='noop' \
    sh -c 'python manage.py tailwind build && python manage.py collectstatic --no-input'
EOF
