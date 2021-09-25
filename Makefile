.PHONY: install-poetry .clear test docs-build docs-serve

.install-poetry:
	deactivate > /dev/null 2>&1 || true
	poetry -V || pip install -U --pre poetry
	touch .install-poetry

install-poetry: .install-poetry

.init: .install-poetry
	rm -rf .venv
	poetry install --default
	git init .
	poetry run pre-commit install --install-hooks
	touch .init

.docs: .init
	poetry install --with docs
	touch .docs

.test: .init
	poetry install --with test
	touch .test

.lint: .init
	poetry install --with lint
	touch .lint

.clear:
	rm -rf .init .docs .test .lint

init: .clear .init

test: .lint .test
	poetry run pre-commit run --all-files
	poetry run pytest -v  --cov --cov-report term

docs-build: .docs
	rm -rf public && mkdir public
	poetry run mkdocs build --site-dir public

docs-serve: .docs
	poetry run mkdocs serve
