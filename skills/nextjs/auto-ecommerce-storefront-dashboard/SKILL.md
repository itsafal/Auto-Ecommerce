---
name: nextjs-auto-ecommerce-storefront-dashboard
description: Use when building or modifying the Auto-Ecommerce Next.js frontend, including subdomain storefront routing, one-product store pages, the internal demo dashboard, run timelines, launch score panels, polling/SSE updates, Tailwind styling, and API integration with FastAPI.
---

# Next.js Storefront And Dashboard

Build one shared Next.js app that renders many one-product stores by subdomain and an internal dashboard for the demo.

## Storefront

1. Use middleware to read the `host` header.
2. Extract the subdomain as `product_slug`.
3. Fetch the matching store config from FastAPI.
4. Render a focused product page with product name, hero image, description, price, CTA, and shipping estimate.

## Dashboard

Required views:

- Trigger run control
- Current run pipeline
- Agent event feed
- Launch score panel
- Store URL result
- Historical run lookup by `run_id`

## Runtime Updates

- Poll `GET /api/runs/{run_id}` and `GET /api/runs/{run_id}/events` every 1-2 seconds for the hackathon build.
- Use Server-Sent Events only if time remains.

## Rules

- Keep the first screen functional, not a marketing landing page.
- Show statuses clearly: `pending`, `running`, `completed`, `failed`, and `fallback_used`.
- Keep dashboard layout dense and scannable.
- Do not depend on live DNS creation; wildcard DNS should route all store slugs to the same app.
