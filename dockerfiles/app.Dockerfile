# syntax=docker/dockerfile:1
FROM python:3.12-alpine as base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

EXPOSE 8000 8443
WORKDIR /app

# Set Timezone
ENV TZ=Asia/Seoul
RUN --mount=type=cache,target=/var/cache/apk <<EOF
  set -eux;
  apk add tzdata;
EOF

RUN --mount=type=cache,target=/var/cache/apk <<EOF
  set -eux;

  # Install System Dependencies
  apk add --virtual .build-deps build-base libc-dev libffi-dev git;

  apk del --no-network .build-deps;

  apk add curl nodejs npm;
EOF

COPY uv.lock /app/uv.lock
COPY pyproject.toml /app/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv <<EOF
  set -eux;
  uv venv
  uv sync --frozen --compile-bytecode --no-install-project;
EOF

# local target
FROM base as local
RUN --mount=type=cache,target=/root/.npm <<EOF
  set -eux;
  npm install -g concurrently;
EOF
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv <<EOF
    set -eux;
    uv sync --frozen --compile-bytecode;
EOF

# prod target
FROM base as prod
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv <<EOF
  set -eux;
  uv sync --frozen --compile-bytecode
  env SECRET_KEY='noop' DB_PASSWORD='noop' DB_HOST='noop' \
    sh -c 'uv run python manage.py tailwind build && uv run python manage.py collectstatic --no-input'
EOF

ENTRYPOINT ["sh", "-c", "uv run python manage.py migrate && uv run gunicorn"]