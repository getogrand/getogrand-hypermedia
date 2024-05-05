# syntax=docker/dockerfile:1
FROM postgres:16-alpine

# Set Timezone
ENV TZ=Asia/Seoul
RUN <<EOF
  set -eux;
  apk add --no-cache tzdata;
EOF
