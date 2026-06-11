import {
  type AgentEvent,
  type LaunchRun,
  type StoreConfig,
  getStoreBySlug,
  mockEvents,
  mockRun,
  mockRunId,
  mockStore
} from "./mock-data";

export type TriggerResponse = {
  run_id: string;
  status: "started";
  temporal_workflow_id: string;
};

export type BatchSlot = {
  slot: number;
  run_id: string;
  product_name: string;
};

export type BatchTriggerResponse = {
  batch_id: string;
  target_count: number;
  threshold: number;
  slots: BatchSlot[];
};

export type BatchRun = LaunchRun & {
  batch_id: string | null;
  batch_slot: number | null;
  attempt_index: number;
  product_attempt?: number;   // plan 04: 1 or 2 — which retry on the current product
  products_tried?: number;    // plan 04: how many distinct products this slot has tried
};

export type BatchStatusResponse = {
  batch_id: string;
  target_count: number;
  threshold: number;
  runs: BatchRun[];
};

export type TopSource = { source: string; share: number };

export type FunnelMetrics = {
  views: number;
  cta_clicks: number;
  checkouts: number;
  email_captures: number;
  purchase_attempts: number;
  cta_rate: number;
  checkout_rate: number;
  capture_rate: number;
  purchase_rate: number;
};

export type Business = {
  run_id: string;
  batch_id: string | null;
  batch_slot: number | null;
  attempt_index: number;
  slug: string;
  product_name: string;
  store_url: string | null;
  launch_score: number | null;
  decision: string;
  status: string;
  business_status: "" | "live" | "shutdown" | "archived";
  launched_at: string | null;
  shutdown_at: string | null;
  shutdown_reason: string;
  days_live: number | null;
  views_total: number;
  views_24h: number;
  revenue_total: number;
  revenue_24h: number;
  conversion_rate: number;
  bounce_rate: number;
  top_sources: TopSource[];
  funnel: FunnelMetrics;
  metric_source: "synthetic" | "events";
};

export type BusinessSummary = {
  live_count: number;
  max_concurrent_live: number;
  total_launched: number;
  total_revenue: number;
  total_views_24h: number;
  hit_rate: number;
  threshold: number;
};

export type BusinessesResponse = {
  data_source: "synthetic" | "events" | "mixed";
  summary: BusinessSummary;
  businesses: Business[];
};

export type BacklogItem = {
  product_name: string;
  category: string;
  source: string;
  trend_score: number;
  detected_at: string;
};

export type BacklogResponse = {
  items: BacklogItem[];
  live_count: number;
  max_concurrent_live: number;
};

export type ShutdownCandidate = {
  slug: string;
  product_name: string;
  reason: string;
  revenue_24h: number;
  conversion_rate: number;
  days_live: number;
};

export type LifecycleTickResult = {
  shutdown_candidates: ShutdownCandidate[];
  shutdowns: Business[];
  promotion: BatchTriggerResponse | null;
  live_count: number;
  max_concurrent_live: number;
};

export type ExperimentChannel = {
  channel: string;
  budget: number;
  objective: string;
};

export type ExperimentPlan = {
  run_id: string;
  slug: string;
  product_name: string;
  daily_budget: number;
  channels: ExperimentChannel[];
};

export type PortfolioExperiments = {
  plans: ExperimentPlan[];
  total_daily_budget: number;
  experiment_count: number;
};

export type CategoryStat = {
  category: string;
  total: number;
  live: number;
  shutdown: number;
  hit_rate: number;
  avg_launch_score: number;
  top_product: string;
};

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
};

export type LLMConfig = {
  provider: "auto" | "anthropic" | "portkey" | "gemini" | "google";
  auto_chain_winner: string;
  anthropic_model: string;
  gemini_model: string;
  portkey_model: string;
  keys_set: { anthropic: boolean; portkey: boolean; gemini: boolean };
};

type ServiceStatus = {
  status: string;
  detail: string;
};

export type HealthSnapshot = {
  clickhouse: ServiceStatus;
  nimble: ServiceStatus;
  llm: LLMConfig;
  runtime: {
    demo_mode: boolean;
    auth_required_for_runs: boolean;
    temporal_enabled: boolean;
    batch_target_count: number;
    launch_score_threshold: number;
    max_concurrent_live: number;
  };
  analytics: ServiceStatus;
  readiness: {
    status: "live_ready" | "needs_attention";
    blockers: string[];
  };
};

export type StorefrontEventType =
  | "view_product"
  | "click_cta"
  | "begin_checkout"
  | "email_capture"
  | "purchase_attempt";

export const useMockMode = () =>
  process.env.NEXT_PUBLIC_USE_MOCKS !== "false" ||
  !process.env.NEXT_PUBLIC_API_BASE_URL;

const apiBaseUrl = () => process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

const authHeaders = (): Record<string, string> => {
  if (typeof window === "undefined") {
    return {};
  }
  const token = window.localStorage.getItem("auto_ecommerce_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
};

type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
  /** Attach the stored bearer token (default true). Login/signup opt out. */
  withAuth?: boolean;
  /** Error message when the backend doesn't supply a `detail`. */
  errorMessage: string;
};

/** Single fetch path for every API call: base URL, JSON encoding, bearer
 *  token, and `detail`-aware error extraction live here so the endpoint
 *  functions below stay one-liners. */
async function request<T>(
  path: string,
  { method = "GET", body, withAuth = true, errorMessage }: RequestOptions
): Promise<T> {
  const headers: Record<string, string> = withAuth ? authHeaders() : {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${apiBaseUrl()}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? errorMessage);
  }
  return response.json();
}

export async function triggerAgentRun(productName: string): Promise<TriggerResponse> {
  if (useMockMode()) {
    return {
      run_id: mockRunId,
      status: "started",
      temporal_workflow_id: `launch-store-${mockRunId}`
    };
  }

  return request("/api/demo/trigger", {
    method: "POST",
    body: { product_name: productName },
    errorMessage: "Failed to trigger agent run"
  });
}

export async function getRun(runId: string): Promise<LaunchRun> {
  if (useMockMode()) {
    return { ...mockRun, run_id: runId };
  }

  return request(`/api/runs/${runId}`, { errorMessage: "Failed to load run" });
}

export async function getRunEvents(runId: string): Promise<{ run_id: string; events: AgentEvent[] }> {
  if (useMockMode()) {
    return { run_id: runId, events: mockEvents };
  }

  return request(`/api/runs/${runId}/events`, { errorMessage: "Failed to load run events" });
}

export async function getStore(slug: string): Promise<StoreConfig> {
  if (useMockMode()) {
    return getStoreBySlug(slug) ?? { ...mockStore, slug };
  }

  return request(`/api/stores/${slug}`, { errorMessage: "Failed to load store" });
}

export async function signup(email: string, password: string, fullName: string): Promise<AuthResponse> {
  return request("/api/auth/signup", {
    method: "POST",
    body: { email, password, full_name: fullName },
    withAuth: false,
    errorMessage: "Failed to create account"
  });
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return request("/api/auth/login", {
    method: "POST",
    body: { email, password },
    withAuth: false,
    errorMessage: "Failed to sign in"
  });
}

export async function getCurrentUser(token: string): Promise<AuthUser> {
  const response = await fetch(`${apiBaseUrl()}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    throw new Error("Session expired");
  }
  return response.json();
}

export async function getTrendingProducts(): Promise<{ products: string[]; source: string }> {
  if (useMockMode()) {
    return {
      products: [
        "Magnetic Phone Mount",
        "Portable Power Station",
        "Red Light Therapy Mask",
        "Mini Portable Projector",
        "Smart Ring Fitness Tracker",
        "Portable Ice Bath",
        "Smart Desk Lamp",
        "Ergo Keyboard"
      ],
      source: "fixture"
    };
  }

  return request("/api/agents/trending-products", {
    errorMessage: "Failed to load trending products"
  });
}

const mockLLMConfig: LLMConfig = {
  provider: "auto",
  auto_chain_winner: "fixture",
  anthropic_model: "claude-haiku-4-5",
  gemini_model: "gemini-2.5-flash-lite",
  portkey_model: "@vertexai/gemini-3.5-flash",
  keys_set: { anthropic: false, portkey: false, gemini: false }
};

const mockHealth: HealthSnapshot = {
  clickhouse: { status: "disabled", detail: "USE_CLICKHOUSE!=true" },
  nimble: { status: "not_configured", detail: "NIMBLE_API_KEY unset" },
  llm: mockLLMConfig,
  runtime: {
    demo_mode: true,
    auth_required_for_runs: true,
    temporal_enabled: false,
    batch_target_count: 5,
    launch_score_threshold: 0.55,
    max_concurrent_live: 5
  },
  analytics: { status: "ready_no_events", detail: "waiting for the first storefront event" },
  readiness: {
    status: "needs_attention",
    blockers: ["mock frontend mode"]
  }
};

export async function triggerBatch(
  body: { count?: number; threshold?: number; products?: string[] } = {}
): Promise<BatchTriggerResponse> {
  if (useMockMode()) {
    const target = body.count ?? 5;
    return {
      batch_id: "mock-batch-0001",
      target_count: target,
      threshold: body.threshold ?? 0.55,
      slots: Array.from({ length: target }, (_, i) => ({
        slot: i,
        run_id: `${mockRunId.slice(0, 8)}-slot${i}`,
        product_name: `Mock Product ${i + 1}`
      }))
    };
  }

  return request("/api/batch/launch", {
    method: "POST",
    body,
    errorMessage: "Failed to start batch"
  });
}

export async function getBatch(batchId: string): Promise<BatchStatusResponse> {
  if (useMockMode()) {
    return {
      batch_id: batchId,
      target_count: 5,
      threshold: 0.55,
      runs: []
    };
  }

  return request(`/api/batch/${batchId}`, { errorMessage: "Failed to load batch" });
}

const mockSummary: BusinessSummary = {
  live_count: 0,
  max_concurrent_live: 5,
  total_launched: 0,
  total_revenue: 0,
  total_views_24h: 0,
  hit_rate: 0,
  threshold: 0.55
};

export async function getBusinesses(
  params: { status?: string; sort?: string } = {}
): Promise<BusinessesResponse> {
  if (useMockMode()) {
    return { data_source: "synthetic", summary: mockSummary, businesses: [] };
  }

  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.sort) qs.set("sort", params.sort);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";

  return request(`/api/businesses${suffix}`, { errorMessage: "Failed to load businesses" });
}

export async function trackStorefrontEvent(
  slug: string,
  event: {
    event_type: StorefrontEventType;
    session_id: string;
    source?: string;
    value?: number;
    metadata?: Record<string, unknown>;
  }
): Promise<void> {
  if (useMockMode()) {
    return;
  }

  await request(`/api/stores/${slug}/events`, {
    method: "POST",
    body: {
      source: "direct",
      value: 0,
      metadata: {},
      ...event
    },
    withAuth: false,
    errorMessage: "Failed to track storefront event"
  });
}

export async function shutdownBusiness(slug: string): Promise<Business> {
  if (useMockMode()) {
    throw new Error("Shutdown not available in mock mode");
  }

  return request(`/api/businesses/${slug}/shutdown`, {
    method: "POST",
    errorMessage: "Failed to shutdown business"
  });
}

export async function getBacklog(limit = 10): Promise<BacklogResponse> {
  if (useMockMode()) {
    return { items: [], live_count: 0, max_concurrent_live: 5 };
  }

  return request(`/api/businesses/backlog?limit=${limit}`, {
    errorMessage: "Failed to load backlog"
  });
}

export async function getLifecycleCandidates(): Promise<{ shutdown_candidates: ShutdownCandidate[] }> {
  if (useMockMode()) {
    return { shutdown_candidates: [] };
  }

  return request("/api/lifecycle/candidates", {
    errorMessage: "Failed to load lifecycle candidates"
  });
}

export async function runLifecycleTick(promote = true): Promise<LifecycleTickResult> {
  if (useMockMode()) {
    return {
      shutdown_candidates: [],
      shutdowns: [],
      promotion: null,
      live_count: 0,
      max_concurrent_live: 5
    };
  }

  return request(`/api/lifecycle/tick?promote=${promote}`, {
    method: "POST",
    errorMessage: "Failed to run lifecycle tick"
  });
}

export async function getPortfolioExperiments(dailyBudget = 50): Promise<PortfolioExperiments> {
  if (useMockMode()) {
    return { plans: [], total_daily_budget: 0, experiment_count: 0 };
  }

  return request(`/api/experiments/portfolio?daily_budget=${dailyBudget}`, {
    errorMessage: "Failed to load experiment plans"
  });
}

export async function getCategoryLeaderboard(): Promise<CategoryStat[]> {
  if (useMockMode()) {
    return [];
  }

  return request("/api/intelligence/category-leaderboard", {
    errorMessage: "Failed to load category leaderboard"
  });
}

export async function getLLMConfig(): Promise<LLMConfig> {
  if (useMockMode()) {
    return mockLLMConfig;
  }

  return request("/api/admin/llm", { errorMessage: "Failed to load LLM config" });
}

export async function getHealth(): Promise<HealthSnapshot> {
  if (useMockMode()) {
    return mockHealth;
  }

  return request("/api/admin/health", { errorMessage: "Failed to load health status" });
}

export async function updateLLMConfig(
  patch: Partial<Pick<LLMConfig, "provider" | "anthropic_model" | "gemini_model" | "portkey_model">>
): Promise<LLMConfig> {
  if (useMockMode()) {
    return { ...mockLLMConfig, ...patch };
  }

  return request("/api/admin/llm", {
    method: "POST",
    body: patch,
    errorMessage: "Failed to update LLM config"
  });
}
