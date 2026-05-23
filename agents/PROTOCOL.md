# A2A Message Protocol

All inter-agent communication uses a single `AgentMessage` envelope defined in `schemas.py`.
No agent calls another agent directly — every handoff goes through the CEO orchestrator.

---

## Pipeline Flow

```
User Input (product_name)
       │
       ▼
  [CEO Orchestrator]
       │
       ├─► [Research Agent] ──── research_complete ───► CEO
       │                    └─── research_failed  ───► CEO (halt)
       │
       ├─► [Buyer Agent]    ──── supplier_selected ──► CEO
       │                    └─── buyer_failed      ──► CEO (halt)
       │
       ├─► [Legal Agent]    ──── legal_cleared ─────► CEO
       │                    └─── legal_flagged   ────► CEO (halt)
       │
       └─► [Advertising Agent] ─ ads_complete ───────► CEO
                                └ ads_failed    ───────► CEO (halt)
                                       │
                               [Store Config assembled]
```

Agents run **sequentially** — each agent receives the accumulated outputs of all prior agents.

---

## Envelope: `AgentMessage`

```python
@dataclass
class AgentMessage:
    from_agent:  AgentName   # "ceo" | "research" | "buyer" | "legal" | "advertising"
    to_agent:    AgentName
    action:      ActionType  # see Action Types below
    payload:     dict        # serialized payload dataclass (empty dict on failure)
    business_id: str         # UUID — ties all messages in a pipeline run together
    message_id:  str         # UUID — unique per message
    timestamp:   datetime    # UTC
    error:       str | None  # set on failure actions only
```

Constructors:
- `AgentMessage.success(from, to, action, payload, business_id)`
- `AgentMessage.failure(from, to, action, business_id, error)`

---

## Action Types

| Action | Direction | Meaning |
|---|---|---|
| `research_complete` | research → ceo | Trend data ready |
| `research_failed` | research → ceo | Pipeline halts |
| `supplier_selected` | buyer → ceo | Best supplier chosen |
| `buyer_failed` | buyer → ceo | Pipeline halts |
| `legal_cleared` | legal → ceo | Product is compliant, proceed |
| `legal_flagged` | legal → ceo | Compliance issue found, pipeline halts |
| `ads_complete` | advertising → ceo | All ad assets generated |
| `ads_failed` | advertising → ceo | Pipeline halts |
| `launch_initiated` | ceo → — | Logged at pipeline start |
| `store_live` | ceo → — | Final store config ready |
| `pipeline_failed` | ceo → — | Logged on any halt |

---

## Payload Schemas

### ResearchPayload (research → ceo)
```
product_name:       str
category:           str                  # e.g. "electronics", "home"
trend_score:        float                # 0–1 from Nimble
search_volume:      int
social_mentions:    int
competitor_prices:  list[float]
estimated_margin:   float                # 0–1
demand_signals:     list[str]            # ["TikTok viral", ...]
raw_nimble_data:    dict
```

### BuyerPayload (buyer → ceo)
```
product_name:             str
selected_supplier:        dict           # {name, price, shipping_days, moq, url}
all_suppliers:            list[dict]
unit_cost:                float
suggested_retail_price:   float
projected_margin:         float          # 0–1
```

### LegalPayload (legal → ceo)
```
product_name:    str
category:        str
cleared:         bool
flags:           list[str]              # ["Possible trademark: 'MagSafe'", ...]
recommendation:  str                    # one-sentence action for operator
risk_level:      "low" | "medium" | "high"
```

### AdvertisingPayload (advertising → ceo)
```
product_name:        str                # polished brand name (not supplier name)
tagline:             str                # ≤ 8 words
ad_copy:             str                # 2–3 sentences
hero_image_prompt:   str                # DALL-E / Stability AI prompt
hero_image_url:      str | None         # generated or scraped fallback
features:            list[str]          # extracted via Claude vision from product image
seo_keywords:        list[str]          # 5–8 keywords
```

---

## Multimodal Input (Advertising Agent)

When Nimble scraping provides a `image_url`, the orchestrator passes it to the Advertising agent.
The agent calls `extract_features_from_image()` which sends the image to Claude vision before
generating ad copy — the extracted features are merged into the generation prompt.

```
Nimble image_url
      │
      ▼
extract_features_from_image()  ──► Claude vision (claude-sonnet-4-6)
      │
      ▼
{features, use_cases, quality_tier, selling_points}
      │
      ▼
Ad generation prompt  ──► Claude (claude-sonnet-4-6)
      │
      ▼
{product_name, tagline, ad_copy, hero_image_prompt, seo_keywords}
      │
      ▼ (if generate_image=True)
_generate_hero_image()  ──► DALL-E 3 (OpenAI)
      │
      ▼
hero_image_url
```

---

## Error Contract

- On any failure, the agent returns `AgentMessage.failure(...)` with `error` set and `payload={}`.
- The CEO orchestrator checks `msg.action == "<agent>_failed"` and calls `_fail()` to halt.
- No agent raises exceptions to the orchestrator — all errors are caught and returned as failure messages.

---

## Adding a New Agent

1. Define a `*Payload` dataclass in `schemas.py`.
2. Add `<agent>_complete` and `<agent>_failed` to the `ActionType` literal in `schemas.py`.
3. Add the agent name to `AgentName` in `schemas.py`.
4. Implement `run_<agent>_agent(..., business_id: str) -> AgentMessage` in a new module.
5. Import and call it in `orchestrator.py` at the correct pipeline step.
