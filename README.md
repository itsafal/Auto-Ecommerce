# Auto-Ecommerce
Auto-Ecommerce is an autonomous multi-agent system that detects niche microtrends and monopolizes on them by automatically launching a full e-commerce store, end to end with no human needed, in minutes. A CEO Orchestrator Agent coordinates a pipeline of specialized sub-agents: the Research Agent uses Nimble to find trending products and competitor prices, a Buyer Agent sources suppliers, a Legal Agent checks compliance, and an Advertising Agent generates copy. Results are stored in ClickHouse for persistence and metrics, with Datadog handling observability across the pipeline, while a Next.js dashboard lets operators trigger runs and watch every agent fire in real time, backed by a FastAPI backend for auth and run management.

## Prerequisites

- Python 3.11+
- `uv`
- Node.js 20+
- Corepack/pnpm

Enable pnpm if needed:

```bash
corepack enable
```

## Environment

Copy the template and keep real secrets only in `.env`:

```bash
cp .env.example .env
```

Minimum local values:

```env
USE_CLICKHOUSE=false
USE_AGENT_FIXTURES=true
USE_TEMPORAL=false
DEMO_MODE=true
AUTH_SECRET=replace-this-with-a-long-random-secret
AUTH_TOKEN_TTL_MINUTES=10080
REQUIRE_AUTH_FOR_RUNS=false
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_USE_MOCKS=false
```

Generate a local auth secret:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

For ClickHouse persistence, set:

```env
USE_CLICKHOUSE=true
CLICKHOUSE_HOST=your-clickhouse-host
CLICKHOUSE_PORT=8443
CLICKHOUSE_USER=your-username
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=your-database
CLICKHOUSE_SECURE=true
```

Do not commit `.env` or real API keys.

## Install

Backend dependencies:

```bash
uv sync
```

Backend dependencies with the open-source Temporal Python SDK:

```bash
uv sync --extra temporal
```

Frontend dependencies:

```bash
cd frontend
corepack pnpm install
```

If pnpm blocks dependency build scripts:

```bash
corepack pnpm approve-builds --all
```

## Run The App

Terminal 1, start the backend in fixture mode:

```bash
USE_CLICKHOUSE=false USE_AGENT_FIXTURES=true USE_TEMPORAL=false uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

PowerShell equivalent:

```powershell
$env:USE_CLICKHOUSE="false"; $env:USE_AGENT_FIXTURES="true"; $env:USE_TEMPORAL="false"; uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2, start the frontend:

```bash
cd frontend
NEXT_PUBLIC_USE_MOCKS=false NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 corepack pnpm dev
```

PowerShell equivalent:

```powershell
cd frontend
$env:NEXT_PUBLIC_USE_MOCKS="false"; $env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"; corepack pnpm dev
```

Open:

- Dashboard: `http://localhost:3000/dashboard`
- Signup: `http://localhost:3000/signup`
- Login: `http://localhost:3000/login`
- Fixture storefront: `http://localhost:3000/store/magneticmount`

## Local Temporal

Temporal Cloud is not required for local development. Use the open-source Temporal SDK with a local Temporal server.

Install the backend Temporal extra:

```bash
uv sync --extra temporal
```

Start a local Temporal dev server in a separate terminal if you have the Temporal CLI installed:

```bash
temporal server start-dev --ip 127.0.0.1 --port 7233
```

Start the worker:

```bash
USE_TEMPORAL=true TEMPORAL_ADDRESS=127.0.0.1:7233 TEMPORAL_NAMESPACE=default uv run python -m backend.workflows.worker
```

Start the API with Temporal enabled:

```bash
USE_CLICKHOUSE=false USE_AGENT_FIXTURES=true USE_TEMPORAL=true TEMPORAL_ADDRESS=127.0.0.1:7233 TEMPORAL_NAMESPACE=default uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

If you do not have the Temporal CLI installed, the test suite and Temporal SDK test environment can still validate the worker/workflow code without any cloud account.

## Render Deployment

This repo includes `render.yaml` for two Render web services:

- `auto-ecommerce-backend`: Python/FastAPI service
- `auto-ecommerce-frontend`: Node/Next.js service

Create a Render Blueprint from this repository's `main` branch. After Render creates the services, set the frontend environment variable:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR-BACKEND-SERVICE.onrender.com
```

Use the public URL of the backend service Render created. Render does not support interpolating one service's public URL into another service's build-time env var in `render.yaml`, so this value must be set in the frontend service settings before deploying the frontend.

For fixture-mode demos on Render, leave:

```env
USE_CLICKHOUSE=false
USE_TEMPORAL=false
USE_AGENT_FIXTURES=true
NEXT_PUBLIC_USE_MOCKS=false
REQUIRE_AUTH_FOR_RUNS=true
```

For real ClickHouse persistence, set `USE_CLICKHOUSE=true` on the backend service and fill in the `CLICKHOUSE_*` secret values in Render. Do not put real secrets in `render.yaml` or `.env.example`.

For real Gemini content generation, set these on the backend service:

```env
USE_AGENT_FIXTURES=false
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
```

For Nimble trend ingestion, set `NIMBLE_API_KEY` and `NIMBLE_API_URL` on the backend service when the Nimble endpoint contract is available.

Useful deployment checks:

```bash
just render-check
just render-env
```

## Smoke Test

Trigger a fixture-backed launch run:

```bash
curl -X POST http://127.0.0.1:8000/api/demo/trigger \
  -H "Content-Type: application/json" \
  -d '{"product_name":"Magnetic Phone Mount"}'
```

Create an account:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"owner@example.com","password":"correct horse battery","full_name":"Store Owner"}'
```

## Tests

Run all backend tests:

```bash
USE_CLICKHOUSE=false USE_AGENT_FIXTURES=true USE_TEMPORAL=false uv run pytest tests -v
```

Run frontend tests:

```bash
cd frontend
corepack pnpm test
```

Run the production frontend build:

```bash
cd frontend
corepack pnpm build
```

## Git Hygiene

The repository ignores local secrets, Python/Node build output, `.DS_Store`, and `.dstore`. If a macOS metadata file is already tracked, remove it with:

```bash
git rm --cached .DS_Store
```
