# Auto-Ecommerce

AI-powered product testing with a FastAPI backend, a Next.js dashboard/storefront, fixture-backed agent runs, and optional ClickHouse persistence.

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
