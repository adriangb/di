#! /usr/bin/env bash
#
# Run parallel commands and fail if any of them fails.
#
set -eu
pids=()
pytest &
pids+=($!)
mypy di &
pids+=($!)
flake8 di &
pids+=($!)
for pid in "${pids[@]}"; do
wait "$pid"
done