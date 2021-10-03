#! /usr/bin/env bash

find . -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete
rm -rf .pytest_cache
rm -rf .mypy_cache

parallel --halt now,fail=1 ::: 'mypy di' 'pytest -x > /dev/null'
