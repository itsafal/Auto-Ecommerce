---
name: pydantic-agent-output-validation
description: Use when defining, validating, or debugging Pydantic schemas for Auto-Ecommerce agent inputs, Gemini/ADK structured outputs, Temporal activity payloads, FastAPI request/response models, ClickHouse event rows, launch scores, or fallback fixtures.
---

# Pydantic Agent Output Validation

Use Pydantic as the contract layer between FastAPI, Temporal activities, ADK agents, ClickHouse writes, and dashboard responses.

## Workflow

1. Define a `BaseModel` for every external boundary:
   - FastAPI request bodies
   - FastAPI responses
   - Temporal activity inputs and outputs
   - ADK/Gemini agent outputs
   - ClickHouse insert payloads
   - demo fixture JSON files
2. Keep agent models small and explicit. Avoid untyped `dict` outputs except at the outer integration edge.
3. Validate model output before writing to ClickHouse or advancing the workflow.
4. On validation failure, emit an `agent_events` row, mark fallback usage, and return a deterministic fixture if `DEMO_MODE=true`.
5. Prefer `model_validate` for Python objects and `model_validate_json` for raw model JSON.

## Required Models

Create or maintain models for:

- `LaunchRun`
- `AgentEvent`
- `ResearchOutput`
- `BuyerOutput`
- `LegalRiskOutput`
- `AdvertisingOutput`
- `SupplierOption`
- `LaunchScore`
- `StoreConfig`

## Rules

- Include `run_id` on every run-scoped model.
- Include `product_slug` where data is tied to a storefront.
- Store scores as floats in the `0.0` to `1.0` range unless the schema documents otherwise.
- Use enums or literal values for statuses such as `pending`, `running`, `completed`, `failed`, and `fallback_used`.
- Do not let raw LLM text drive control flow until it validates against a Pydantic model.
