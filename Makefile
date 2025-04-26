.EXPORT_ALL_VARIABLES:

# EVENTSTORE_DOCKER_IMAGE ?= eventstore/eventstore:23.10.0-bookworm-slim
EVENTSTORE_DOCKER_IMAGE ?= docker.eventstore.com/eventstore/eventstoredb-ee:24.10.0-x64-8.0-bookworm-slim

PYTHONUNBUFFERED=1

POETRY_VERSION=2.1.2
POETRY ?= poetry@$(POETRY_VERSION)

.PHONY: install-poetry
install-poetry:
	@pipx install --suffix="@$(POETRY_VERSION)" "poetry==$(POETRY_VERSION)"
	$(POETRY) --version

.PHONY: install
install:
	$(POETRY) sync  -vv $(opts)

.PHONY: install-packages
install-packages:
	$(POETRY) sync --no-root -vv $(opts)

.PHONY: update-lockfile
update-lockfile:
	$(POETRY) lock

.PHONY: update-packages
update-packages: update-lockfile install-packages


.PHONY: install-pre-commit-hooks
install-pre-commit-hooks:
ifeq ($(opts),)
	$(POETRY) run pre-commit install
endif

.PHONY: uninstall-pre-commit-hooks
uninstall-pre-commit-hooks:
ifeq ($(opts),)
	$(POETRY) run pre-commit uninstall
endif

.PHONY: lock-packages
lock-packages:
	$(POETRY) lock -vv --no-update

.PHONY: update-packages
update-packages:
	$(POETRY) update -vv

.PHONY: lint-black
lint-black:
	$(POETRY) run black --check --diff .

.PHONY: lint-flake8
lint-flake8:
	$(POETRY) run flake8

.PHONY: lint-isort
lint-isort:
	$(POETRY) run isort --check-only --diff .

.PHONY: lint-mypy
lint-mypy:
	$(POETRY) run mypy

.PHONY: lint-python
lint-python: lint-black lint-flake8 lint-isort lint-mypy

.PHONY: lint
lint: lint-python

.PHONY: fmt-black
fmt-black:
	$(POETRY) run black .

.PHONY: fmt-isort
fmt-isort:
	$(POETRY) run isort .

.PHONY: fmt
fmt: fmt-black fmt-isort

.PHONY: test
test:
	$(POETRY) run coverage run -m unittest discover . -v
	$(POETRY) run coverage report --fail-under=100 --show-missing

.PHONY: build
build:
	$(POETRY) build
# 	$(POETRY) build -f sdist    # build source distribution only

.PHONY: publish
publish:
	$(POETRY) publish

.PHONY: start-eventstoredb-insecure
start-eventstoredb-insecure:
	docker run -d -i -t -p 2113:2113 \
    --env "EVENTSTORE_ADVERTISE_HOST_TO_CLIENT_AS=localhost" \
    --env "EVENTSTORE_ADVERTISE_HTTP_PORT_TO_CLIENT_AS=2113" \
    --name my-eventstoredb-insecure \
    $(EVENTSTORE_DOCKER_IMAGE) \
    --insecure \
    --enable-atom-pub-over-http

.PHONY: start-eventstoredb-secure
start-eventstoredb-secure:
	docker run -d -i -t -p 2114:2113 \
    --env "HOME=/tmp" \
    --env "EVENTSTORE_ADVERTISE_HOST_TO_CLIENT_AS=localhost" \
    --env "EVENTSTORE_ADVERTISE_HTTP_PORT_TO_CLIENT_AS=2114" \
    --name my-eventstoredb-secure \
    $(EVENTSTORE_DOCKER_IMAGE) \
    --dev

.PHONY: attach-eventstoredb-insecure
attach-eventstoredb-insecure:
	docker exec -it my-eventstoredb-insecure /bin/bash

.PHONY: attach-eventstoredb-secure
attach-eventstoredb-secure:
	docker exec -it my-eventstoredb-secure /bin/bash

.PHONY: stop-eventstoredb-insecure
stop-eventstoredb-insecure:
	docker stop my-eventstoredb-insecure
	docker rm my-eventstoredb-insecure

.PHONY: stop-eventstoredb-secure
stop-eventstoredb-secure:
	docker stop my-eventstoredb-secure
	docker rm my-eventstoredb-secure

.PHONY: start-eventstoredb
start-eventstoredb: start-eventstoredb-insecure start-eventstoredb-secure
	@echo "Waiting for containers to be healthy"
	@until docker ps | grep "my-eventstoredb" | grep -in "healthy" | wc -l | grep -in 2 > /dev/null; do printf "." && sleep 1; done; echo ""
	@docker ps
	@sleep 15


.PHONY: stop-eventstoredb
stop-eventstoredb: stop-eventstoredb-insecure stop-eventstoredb-secure
