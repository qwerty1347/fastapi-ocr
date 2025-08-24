#!/bin/sh
set -e

exec uvicorn main:app --reload --host 0.0.0.0 --port 8000