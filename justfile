set dotenv-load := true

backend_port := "8000"
frontend_port := "3000"

backend:
    USE_CLICKHOUSE="${USE_CLICKHOUSE:-false}" USE_AGENT_FIXTURES="${USE_AGENT_FIXTURES:-true}" USE_TEMPORAL="${USE_TEMPORAL:-false}" uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port {{backend_port}}

frontend:
    cd frontend && NEXT_PUBLIC_USE_MOCKS="${NEXT_PUBLIC_USE_MOCKS:-false}" NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://127.0.0.1:{{backend_port}}}" corepack pnpm exec next dev -p {{frontend_port}}

backend-build:
    pip install uv
    uv sync --extra temporal --frozen

frontend-build:
    cd frontend && npm exec --yes --package=pnpm@11.2.2 -- pnpm install --frozen-lockfile && npm exec --yes --package=pnpm@11.2.2 -- pnpm build

render-check:
    just backend-build
    just frontend-build

render-env:
    @echo "Backend Render service:"
    @echo "  Build: pip install uv && uv sync --extra temporal --frozen"
    @echo "  Start: uv run uvicorn backend.main:app --host 0.0.0.0 --port \\$PORT"
    @echo
    @echo "Frontend Render service:"
    @echo "  Root dir: frontend"
    @echo "  Build: npm exec --yes --package=pnpm@11.2.2 -- pnpm install --frozen-lockfile && npm exec --yes --package=pnpm@11.2.2 -- pnpm build"
    @echo "  Start: ./node_modules/.bin/next start -H 0.0.0.0 -p \\$PORT"
    @echo
    @echo "Set NEXT_PUBLIC_API_BASE_URL on the frontend to the backend Render URL."

check-ports:
    #!/usr/bin/env bash
    set -euo pipefail

    busy=0
    for port in {{backend_port}} {{frontend_port}}; do
      if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        echo "Port $port is already in use:"
        lsof -nP -iTCP:"$port" -sTCP:LISTEN
        busy=1
      fi
    done

    if [[ "$busy" -ne 0 ]]; then
      echo
      echo "Run 'just down' to stop the existing dev servers, then run 'just up' again."
      exit 1
    fi

up: check-ports
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

    for port in {{backend_port}} {{frontend_port}}; do
      pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
      if [[ -n "$pids" ]]; then
        echo "Stopping processes on port $port: $pids"
        kill $pids 2>/dev/null || true
      fi
    done

    sleep 1

    for port in {{backend_port}} {{frontend_port}}; do
      pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
      if [[ -n "$pids" ]]; then
        echo "Force stopping processes on port $port: $pids"
        kill -9 $pids 2>/dev/null || true
      fi
    done
