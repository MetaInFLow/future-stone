#!/usr/bin/env bash
set -euo pipefail

pnpm install
cd services/backend-api
uv sync --extra dev

