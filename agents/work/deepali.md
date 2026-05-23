# Deepali — Agent Work Package

## Files You Own
| File | Status |
|------|--------|
| `schemas.py` | Done — A2A message protocol, all payload types |
| `orchestrator.py` | Done — CEO pipeline: Research → Buyer → Legal → Advertising |
| `legal.py` | Done — Claude-powered compliance check |
| `advertising.py` | Done — Claude copywriter + multimodal image feature extraction |

---

## How to Run

### Option A — With just Nimble key (no Anthropic key yet)

Legal + Advertising agents return realistic mock data automatically when `ANTHROPIC_API_KEY` is not set.

```bash
cd /Users/deepalibalakrishna/Downloads

# Install deps
pip install anthropic httpx

# Run with Nimble doing real trend research, Claude agents in mock mode
NIMBLE_API_KEY=your_key_here python -m agents.main "ergonomic keyboard"

# Or pass any product
NIMBLE_API_KEY=your_key_here python -m agents.main "magnetic phone mount"
```

### Option B — Full demo mode (no API keys at all)

All agents return hardcoded fixture data. Use this to test the pipeline shape end-to-end.

```bash
cd /Users/deepalibalakrishna/Downloads
DEMO_MODE=true python -m agents.main "ergonomic keyboard"
```

### Option C — Full live run (all APIs active)

```bash
cd /Users/deepalibalakrishna/Downloads
NIMBLE_API_KEY=... ANTHROPIC_API_KEY=sk-ant-... python -m agents.main "ergonomic keyboard"

# With Claude vision + image gen flag
NIMBLE_API_KEY=... ANTHROPIC_API_KEY=... python -m agents.main "ergonomic keyboard" \
  --image-url "https://example.com/product.jpg"
```

---

## What Each Agent Returns (Your Outputs)

### Legal Agent (`legal.py`)
```json
{
  "cleared": true,
  "risk_level": "low",
  "flags": [],
  "recommendation": "Safe to sell. No trademark or import restrictions found.",
  "reasoning": "Generic consumer electronics with no known conflicts."
}
```
Pipeline **halts** if `cleared=false`. Orchestrator logs the flags and exits.

### Advertising Agent (`advertising.py`)
```json
{
  "product_name": "ErgoSnap Pro",
  "tagline": "Typing that doesn't hurt.",
  "ad_copy": "...",
  "hero_image_prompt": "product photo, white background, studio lighting...",
  "hero_image_url": null,
  "features": ["compact tenkeyless layout", "tactile switches"],
  "seo_keywords": ["ergonomic keyboard", "best ergonomic keyboard", ...]
}
```

---

## Demo Env Setup (before hackathon)

```bash
# .env (never commit this)
NIMBLE_API_KEY=your_nimble_key
ANTHROPIC_API_KEY=sk-ant-...        # get from console.anthropic.com
DEMO_MODE=false                     # set true for safe fallback during demo
```

---

## Remaining TODOs

- [ ] Wire `DEMO_MODE=true` fallback into demo trigger endpoint (Ali's dashboard button)
- [ ] Confirm `legal_flagged` halt behavior with Dipesh (he tests the CEO flow)
- [ ] Test multimodal path: pass a real Nimble `image_url` and confirm feature extraction works
- [ ] Coordinate with Safal: make sure `store_config` JSON from orchestrator matches frontend shape
- [ ] If Anthropic key arrives: flip `DEMO_MODE=false` and test live Legal + Advertising
