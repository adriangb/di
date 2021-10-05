.PHONY: install-poetry .clear test test-mutation docs-build docs-serve

GIT_SHA = $(shell git rev-parse --short HEAD)
PACKAGE_VERSION = $(shell poetry version -s | cut -d+ -f1)

.install-poetry:
	@echo "---- 👷 Installing build dependencies ----"
	deactivate > /dev/null 2>&1 || true
	pip install -U pip wheel
	poetry -V || pip install -U --pre poetry
	touch .install-poetry

install-poetry: .install-poetry

.init: .install-poetry
	@echo "---- 📦 Building package ----"
	rm -rf .venv
	poetry install --default
	touch .init

.docs: .init
	@echo "---- 📄 Installing doc dependencies ----"
	poetry install --only docs
	touch .docs

.test: .init
	@echo "---- 🧪 Installing test dependencies ----"
	poetry install --only test
	touch .test

.lint: .init
	@echo "---- 👕 Installing lint dependencies ----"
	poetry install --only lint
	git init .
	poetry run pre-commit install --install-hooks
	touch .lint

.clean:
	rm -rf .init .docs .test .lint .mypy_cache .pytest_cache
	poetry -V || rm -rf .install-poetry

init: .clean .init .lint
	@echo ---- 🔧 Re-initialized project ----

lint: .lint .test  # need the tests deps for linting of test fils to work
	@echo ---- ⏳ Running linters ----
	@(poetry run pre-commit run --all-files && echo "---- ✅ Linting passed ----" && exit 0|| echo "---- ❌ Linting failed ----" && exit 1)

test: .test
	@echo ---- ⏳ Running tests ----
	@(poetry run pytest -v --cov --cov-report term && echo "---- ✅ Tests passed ----" && exit 0 || echo "---- ❌ Tests failed ----" && exit 1)

test-mutation: .test
	@echo ---- ⏳ Running mutation testing ----
	@poetry run python -m pip install mutmut
	@(poetry run pytest --cov && poetry run mutmut run --use-coverage && echo "---- ✅ Passed ----" && exit 0 || echo "---- ❌ Failed ----" && exit 1)

.netlify-build-docs: .install-poetry
	rm -rf public && mkdir public
	poetry install --default --only docs
	poetry run mkdocs build --site-dir public

docs-serve: .docs
	@echo ---- 📝 Serving docs ----
	@poetry run mkdocs serve

docs-deploy: .docs
	@echo ---- 🚀 Deploying docs ----
	@(poetry run mike deploy --push --update-aliases --branch gh-docs $(shell poetry version -s) latest && echo "---- ✅ Deploy succeeded ----" && exit 0 || echo "---- ❌ Deploy failed ----" && exit 1)
