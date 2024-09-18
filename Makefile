.PHONY: dev
dev:
	docker compose -f compose.base.yaml -f compose.local.yaml up --build

.PHONY: prod
prod:
	UPSTREAMS="app:8000" DEBUG="False" \
	docker compose -f compose.base.yaml -f compose.prod.yaml up --build

.PHONY: manage
manage:
	docker compose -f compose.base.yaml -f compose.local.yaml run --build app \
	python manage.py shell

.PHONY: build
build:
	docker compose -f compose.base.yaml -f compose.prod.yaml build

.PHONY: push
push:
	docker compose -f compose.base.yaml -f compose.prod.yaml push

.PHONY: ecr-login
ecr-login:
	aws ecr get-login-password --region ap-northeast-2 | \
	docker login --username AWS --password-stdin 730335367003.dkr.ecr.ap-northeast-2.amazonaws.com

.PHONY: deploy
deploy: ecr-login build push

.PHONY: purge
purge:
	aws cloudfront create-invalidation --distribution-id=E1QKQUFSZNE1WL --paths='/*'