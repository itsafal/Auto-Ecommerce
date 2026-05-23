set dotenv-load := true

backend:
    USE_CLICKHOUSE="${USE_CLICKHOUSE:-false}" USE_AGENT_FIXTURES="${USE_AGENT_FIXTURES:-true}" USE_TEMPORAL="${USE_TEMPORAL:-false}" uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

frontend:
    cd frontend && NEXT_PUBLIC_USE_MOCKS="${NEXT_PUBLIC_USE_MOCKS:-false}" NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://127.0.0.1:8000}" corepack pnpm dev

up:
    #!/usr/bin/env bash
    set -euo pipefail

    just backend &
    backend_pid=$!

    just frontend &
    frontend_pid=$!

    cleanup() {
      kill "$backend_pid" "$frontend_pid" 2>/dev/null || true
      wait "$backend_pid" "$frontend_pid" 2>/dev/null || true
    }

    trap cleanup EXIT INT TERM
    wait "$backend_pid" "$frontend_pid"

down:
    #!/usr/bin/env bash
    set -euo pipefail

    pkill -f "uvicorn backend.main:app" 2>/dev/null || true
    pkill -f "next dev" 2>/dev/null || true
