.EXPORT_ALL_VARIABLES:

POETRY ?= poetry
POETRY_INSTALLER_URL ?= https://install.python-poetry.org


.PHONY: install-poetry
install-poetry:
	curl -sSL $(POETRY_INSTALLER_URL) | python3
	$(POETRY) --version

.PHONY: install-packages
install-packages:
	$(POETRY) install -vv $(opts)

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
	$(POETRY) run python -m pytest -v $(opts) $(call tests,.)

.PHONY: build
build:
	$(POETRY) build
# 	$(POETRY) build -f sdist    # build source distribution only

.PHONY: publish
publish:
	$(POETRY) publish

.PHONY: start-eventstoredb
start-eventstoredb: start-eventstoredb-22-10

.PHONY: start-eventstoredb-21-10
start-eventstoredb-21-10:
	docker run -d --name my-eventstoredb -it -p 2113:2113 -p 1113:1113 eventstore/eventstore:21.10.9-buster-slim --insecure

.PHONY: start-eventstoredb-22-10
start-eventstoredb-22-10:
	docker run -d --name my-eventstoredb -it -p 2113:2113 -p 1113:1113 eventstore/eventstore:22.10.0-buster-slim --insecure

.PHONY: stop-eventstoredb
stop-eventstoredb:
	docker stop my-eventstoredb
	docker rm my-eventstoredb
