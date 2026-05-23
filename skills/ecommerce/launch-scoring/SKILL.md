---
name: ecommerce-launch-scoring
description: Use when designing or modifying Auto-Ecommerce launch decision logic, including trend score, margin score, supplier confidence, compliance risk, final launch/no-launch decisions, dashboard score explanations, and ClickHouse analytics for retries or near-miss products.
---

# Ecommerce Launch Scoring

Use a simple, explainable score so judges can understand why the system launches or rejects a product.

## Formula

```python
launch_score = (
    trend_score * 0.30
    + margin_score * 0.25
    + supplier_confidence * 0.25
    - compliance_risk * 0.20
)
```

## Inputs

- `trend_score`: demand and market signal
- `margin_score`: estimated profit margin quality
- `supplier_confidence`: supplier rating, shipping speed, cost, and reliability
- `compliance_risk`: trademark, regulated product, shipping, and ad claim risk

## Output

Return:

- `launch_score`
- component scores
- `decision`: `launch`, `pause`, or `reject`
- short explanation
- flags that affected the decision

## Rules

- Keep all component scores normalized from `0.0` to `1.0`.
- Show the score and explanation in the dashboard before store creation.
- Store launch decisions in ClickHouse with the `run_id`.
- Bias/retry logic should favor near-misses when trend score improves and risk remains acceptable.
