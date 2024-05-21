# syntax=docker/dockerfile:1
FROM caddy:2-alpine

# Set Timezone
ENV TZ=Asia/Seoul
RUN <<EOF
  set -eux;
  apk add --no-cache tzdata;
EOF

COPY ./Caddyfile /etc/caddy/Caddyfile

EXPOSE 8000 8443
