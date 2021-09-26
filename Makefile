.PHONY: install-poetry .clear test docs-build docs-serve

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
	poetry install --with docs
	touch .docs

.test: .init
	@echo "---- 🧪 Installing test dependencies ----"
	poetry install --with test
	touch .test

.lint: .init
	@echo "---- 👕 Installing lint dependencies ----"
	poetry install --with lint
	git init .
	poetry run pre-commit install --install-hooks
	touch .lint

.clear:
	rm -rf .init .docs .test .lint
	poetry -V || rm -rf .install-poetry

init: .clear .init
	@echo ---- 🔧 Re-initializing project ----

lint: .lint .test  # need the tests deps for linting of test fils to work
	@echo ---- ⏳ Running linters ----
	@(poetry run pre-commit run --all-files && echo "---- ✅ Linting passed ----" || echo "---- ❌ Linting failed ----")

test: .test
	@echo ---- ⏳ Running tests ----
	@(poetry run pytest -v --cov --cov-report term && echo "---- ✅ Tests passed ----" || echo "---- ❌ Tests failed ----")

.netlify-build-docs: .init
	rm -rf public && mkdir public
	poetry export -f requirements.txt --output requirements.txt --dev
	pip install -r requirements.txt
	poetry run mkdocs build --site-dir public

docs-serve: .docs
	@echo ---- 📝 Serving docs ----
	@poetry run mkdocs serve

docs-deploy: .docs
	@echo ---- 📝 Deploying docs ----
	@poetry run mike deploy --push --update-aliases --branch gh-docs $(shell poetry version -s) latest
