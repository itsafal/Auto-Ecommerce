# Deepali Work Plan

## Mission

Own the Google ADK + Gemini agent layer. Build each agent as an independently testable module with fixture-backed outputs.

No real Gemini key is required for the first pass. Provide mock runners that return validated JSON matching the integration guide.

## Independent Boundary

You own:

- `backend/agents/base.py`
- `backend/agents/research.py`
- `backend/agents/buyer.py`
- `backend/agents/legal.py`
- `backend/agents/advertising.py`
- `backend/agents/runner.py`
- `backend/fixtures/agent_outputs/research.json`
- `backend/fixtures/agent_outputs/buyer.json`
- `backend/fixtures/agent_outputs/legal.json`
- `backend/fixtures/agent_outputs/advertising.json`
- `tests/agents/test_research_agent.py`
- `tests/agents/test_buyer_agent.py`
- `tests/agents/test_legal_agent.py`
- `tests/agents/test_advertising_agent.py`

Do not own Temporal orchestration. Deepesh will call your agents from Temporal activities.

## Build Tasks

1. Define one small interface for all agents.
   - Input: dictionary matching `work/integration-guide.md`.
   - Output: validated Pydantic object or dictionary.
2. Build Research Agent with Google ADK.
   - Model: `gemini-flash-latest`
   - Output fields:
     - `trend_score`
     - `search_volume`
     - `social_mentions`
     - `competitor_summary`
     - `price_range`
     - `confidence`
3. Build Buyer Agent with Google ADK.
   - Output fields:
     - `supplier_name`
     - `unit_cost`
     - `shipping_days`
     - `rating`
     - `estimated_margin`
     - `confidence_score`
     - `risk_flags`
4. Build Legal / Risk Agent with Google ADK.
   - Output fields:
     - `cleared`
     - `risk_score`
     - `flags`
     - `recommendation`
5. Build Advertising Agent with Google ADK.
   - Output fields:
     - `product_name`
     - `tagline`
     - `description`
     - `cta_text`
     - `hero_image_prompt`
     - `hero_image_url`
6. Add fixture mode.
   - Env var: `USE_AGENT_FIXTURES=true`.
   - When true, return JSON fixtures instead of calling Gemini.
7. Add local CLI trigger for each agent.

## Trigger Requirement

Each agent must be triggerable independently without API keys.

Example:

```bash
USE_AGENT_FIXTURES=true uv run python -m backend.agents.runner research \
  --product "Magnetic Phone Mount"
```

Expected output:

```json
{
  "agent": "research",
  "product_name": "Magnetic Phone Mount",
  "trend_score": 0.86,
  "confidence": 0.82
}
```

Add equivalent triggers:

```bash
USE_AGENT_FIXTURES=true uv run python -m backend.agents.runner buyer --product "Magnetic Phone Mount"
USE_AGENT_FIXTURES=true uv run python -m backend.agents.runner legal --product "Magnetic Phone Mount"
USE_AGENT_FIXTURES=true uv run python -m backend.agents.runner advertising --product "Magnetic Phone Mount"
```

## Tests

Add tests:

- `research fixture output validates`
- `buyer fixture output validates`
- `legal fixture output validates`
- `advertising fixture output validates`
- `runner dispatches correct agent`
- `agent outputs contain no markdown fences`
- `agent outputs are JSON-serializable`

Suggested command:

```bash
USE_AGENT_FIXTURES=true uv run pytest tests/agents -v
```

## Done Criteria

- All four specialist agents exist.
- Each can be triggered independently.
- No API keys are required in fixture mode.
- Outputs match `work/integration-guide.md`.
- Tests pass locally.
