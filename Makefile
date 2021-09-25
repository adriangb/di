.PHONY: install-poetry .clear-init check-version test publish docs

.install-poetry:
	deactivate > /dev/null 2>&1 || true
	poetry -V || pip install -U --pre poetry
	touch .install-poetry

install-poetry: .install-poetry

.init: .install-poetry
	rm -rf .venv
	poetry install
	git init .
	poetry run pre-commit install --install-hooks
	touch .init

.clear-init:
	rm -rf .init

init: .clear-init .init

test: .init
	poetry run pre-commit run --all-files
	poetry run pytest -v  --cov --cov-report term

docs-build: .init
	rm -rf public && mkdir public
	poetry run mkdocs build --site-dir public

docs-serve: .init
	poetry run mkdocs serve
