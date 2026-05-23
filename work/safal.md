# Safal Work Plan

## Mission

Own the frontend experience: micro-store rendering, dashboard control room, live agent timeline visualization, launch score panel, and UI trigger.

Your work should run against mocked API responses first. Do not wait for backend integration.

## Independent Boundary

You own:

- `frontend/app/page.tsx`
- `frontend/app/store/[slug]/page.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/middleware.ts`
- `frontend/components/StoreTemplate.tsx`
- `frontend/components/AgentTimeline.tsx`
- `frontend/components/AgentFeed.tsx`
- `frontend/components/LaunchScore.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/mock-data.ts`
- `frontend/tests/dashboard.test.tsx`
- `frontend/tests/store-template.test.tsx`

Do not depend on the live backend. Build the UI against `frontend/lib/mock-data.ts` and one typed API client.

## Build Tasks

1. Create the Next.js app structure.
2. Add middleware for subdomain routing.
   - `magneticmount.fastaisolution.com` maps to `/store/magneticmount`.
3. Build `StoreTemplate`.
   - Product name
   - Hero image
   - Description
   - Price
   - CTA
   - Supplier/shipping note
4. Build dashboard page.
   - Product input or dropdown
   - `Trigger Agent Run` button
   - Current `run_id`
   - Agent timeline
   - Launch score panel
   - Live event feed
   - Final store URL
5. Build `AgentTimeline`.
   - Steps:
     - Research
     - Buyer
     - Legal / Risk
     - Advertising
     - Store Creator
   - States:
     - pending
     - running
     - completed
     - failed
     - fallback used
6. Build `LaunchScore`.
   - trend score
   - margin score
   - supplier confidence
   - compliance risk
   - final launch/no-launch result
7. Add polling behavior.
   - After trigger, call `GET /api/runs/{run_id}` and `GET /api/runs/{run_id}/events`.
   - Poll every 1-2 seconds.
8. Add mocked mode.
   - If `NEXT_PUBLIC_USE_MOCKS=true`, use `mock-data.ts`.

## Trigger Requirement

You must provide a UI trigger that works without backend keys:

1. Open `/dashboard`.
2. Enter or select `Magnetic Phone Mount`.
3. Click `Trigger Agent Run`.
4. The timeline should animate or update through all agent states using mock data.

Expected UI result:

- A visible `run_id`
- Timeline shows agent progress
- Launch score is visible
- Final store URL appears:
  - `https://magneticmount.fastaisolution.com`

## Tests

Add frontend tests:

- `dashboard renders trigger button`
- `clicking trigger creates visible run_id in mock mode`
- `agent timeline renders all five steps`
- `launch score renders all score components`
- `store template renders product config`
- `middleware extracts subdomain slug`

Suggested command:

```bash
pnpm test
```

If test tooling is not set up yet, add Vitest + React Testing Library.

## Done Criteria

- Dashboard works with mock data.
- Store template works with mock product config.
- UI trigger can simulate a full agent run without backend.
- API client contracts match `work/integration-guide.md`.
- Tests pass locally.
