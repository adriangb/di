.PHONY: .clean test test-mutation docs-build docs-serve

GIT_SHA = $(shell git rev-parse --short HEAD)
PACKAGE_VERSION = $(shell poetry version -s | cut -d+ -f1)

.init:
	@echo "---- 📦 Building package ----"
	deactivate > /dev/null 2>&1 || true
	poetry -V || pip install -U --pre poetry
	rm -rf .venv
	deactivate || true
	poetry install
	git init .
	poetry run pre-commit install --install-hooks
	touch .init

.clean:
	rm -rf .init .mypy_cache .pytest_cache

init: .clean .init
	@echo ---- 🔧 Re-initialized project ----

lint: .init
	@echo ---- ⏳ Running linters ----
	@(poetry run pre-commit run --all-files && echo "---- ✅ Linting passed ----" && exit 0|| echo "---- ❌ Linting failed ----" && exit 1)

test: .init
	@echo ---- ⏳ Running tests ----
	@(poetry run pytest -v --cov --cov-report term && echo "---- ✅ Tests passed ----" && exit 0 || echo "---- ❌ Tests failed ----" && exit 1)

test-mutation: .init
	@echo ---- ⏳ Running mutation testing ----
	@poetry run python -m pip install mutmut
	@(poetry run pytest --cov && poetry run mutmut run --use-coverage && echo "---- ✅ Passed ----" && exit 0 || echo "---- ❌ Failed ----" && exit 1)

docs-serve: .init
	@echo ---- 📝 Serving docs ----
	@poetry run mkdocs serve

docs-deploy: .init
	@echo ---- 🚀 Deploying docs ----
	@(poetry run mike deploy --push --update-aliases --branch gh-docs $(shell poetry version -s) latest && echo "---- ✅ Deploy succeeded ----" && exit 0 || echo "---- ❌ Deploy failed ----" && exit 1)
