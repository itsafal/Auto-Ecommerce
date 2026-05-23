# Auto-Ecommerce

## Backend fixture mode

Run the backend tests:

```bash
USE_TEMPORAL=false uv run pytest tests/backend -v
```

Start the FastAPI backend without Temporal or API keys:

```bash
USE_TEMPORAL=false uv run uvicorn backend.main:app --reload
```

Trigger a fixture-backed launch run:

```bash
curl -X POST http://localhost:8000/api/demo/trigger \
  -H "Content-Type: application/json" \
  -d '{"product_name":"Magnetic Phone Mount"}'
```
