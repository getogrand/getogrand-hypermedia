# syntax=docker/dockerfile:1
FROM --platform=arm64 caddy:2-alpine

# Set Timezone
ENV TZ=Asia/Seoul
RUN <<EOF
  set -eux;
  apk add --no-cache tzdata;
EOF
