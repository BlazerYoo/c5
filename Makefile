HOST_UID := $(shell id -u)
HOST_GID := $(shell id -g)
HOST_USER := $(shell whoami)

COMPOSE_ENV = HOST_UID=$(HOST_UID) HOST_GID=$(HOST_GID) HOST_USER=$(HOST_USER)

NAME = claude-dev

.PHONY: up shell

up:
	$(COMPOSE_ENV) docker compose run --rm --build --name $(NAME) claude

shell:
	docker exec -it $(NAME) bash
