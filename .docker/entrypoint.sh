#!/bin/sh
set -e

exec uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000