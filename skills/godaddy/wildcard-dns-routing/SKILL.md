---
name: godaddy-wildcard-dns-routing
description: Use when configuring Auto-Ecommerce domain routing with GoDaddy, wildcard DNS for fastaisolution.com, subdomain-based storefront routing, DNS demo safety, optional GoDaddy API cleanup, and avoiding live DNS provisioning on the critical demo path.
---

# GoDaddy Wildcard DNS Routing

Use wildcard DNS so every store slug routes to the same deployed frontend.

## Required Setup

Configure:

```text
*.fastaisolution.com -> deployed frontend target
```

The exact record type depends on the hosting target. Use the provider's domain instructions for whether the wildcard should be an `A`, `CNAME`, or platform-specific record.

## Routing Model

1. DNS sends all subdomains to the frontend.
2. Next.js middleware extracts the subdomain.
3. The frontend fetches store config by slug.
4. No per-store deployment is required.

## Rules

- Do not depend on live DNS creation during the demo.
- Set and test wildcard DNS before the demo.
- Use GoDaddy API only for optional cleanup or record management after the core path works.
- Keep `BASE_DOMAIN=fastaisolution.com` in backend configuration.
