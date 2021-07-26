.PHONY: install-poetry .clear-init check-version test publish docs

.install-poetry:
	deactivate > /dev/null 2>&1 || true
	pip install -U --pre poetry
	touch .install-poetry

install-poetry: .install-poetry

.init: .install-poetry
	rm -rf poetry.lock
	rm -rf $(poetry env info -p) > /dev/null 2>&1 || true
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

docs:
	@echo "serving docs at http://localhost:8008"
	python -m http.server 8008
