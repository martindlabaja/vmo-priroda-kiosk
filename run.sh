#!/bin/bash
# Run Flask development server locally

cd "$(dirname "$0")"
./venv/bin/python -m flask --app server.app run --port 5000
