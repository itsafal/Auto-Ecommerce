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
  data_source: "synthetic";
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

export async function triggerAgentRun(productName: string): Promise<TriggerResponse> {
  if (useMockMode()) {
    return {
      run_id: mockRunId,
      status: "started",
      temporal_workflow_id: `launch-store-${mockRunId}`
    };
  }

  const response = await fetch(`${apiBaseUrl()}/api/demo/trigger`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ product_name: productName })
  });
  if (!response.ok) {
    throw new Error("Failed to trigger agent run");
  }
  return response.json();
}

export async function getRun(runId: string): Promise<LaunchRun> {
  if (useMockMode()) {
    return { ...mockRun, run_id: runId };
  }

  const response = await fetch(`${apiBaseUrl()}/api/runs/${runId}`);
  if (!response.ok) {
    throw new Error("Failed to load run");
  }
  return response.json();
}

export async function getRunEvents(runId: string): Promise<{ run_id: string; events: AgentEvent[] }> {
  if (useMockMode()) {
    return { run_id: runId, events: mockEvents };
  }

  const response = await fetch(`${apiBaseUrl()}/api/runs/${runId}/events`);
  if (!response.ok) {
    throw new Error("Failed to load run events");
  }
  return response.json();
}

export async function getStore(slug: string): Promise<StoreConfig> {
  if (useMockMode()) {
    return getStoreBySlug(slug) ?? { ...mockStore, slug };
  }

  const response = await fetch(`${apiBaseUrl()}/api/stores/${slug}`);
  if (!response.ok) {
    throw new Error("Failed to load store");
  }
  return response.json();
}

export async function signup(email: string, password: string, fullName: string): Promise<AuthResponse> {
  const response = await fetch(`${apiBaseUrl()}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName })
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? "Failed to create account");
  }
  return response.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${apiBaseUrl()}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? "Failed to sign in");
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

  const response = await fetch(`${apiBaseUrl()}/api/agents/trending-products`);
  if (!response.ok) {
    throw new Error("Failed to load trending products");
  }
  return response.json();
}

export type LLMConfig = {
  provider: "auto" | "anthropic" | "portkey" | "gemini" | "google";
  auto_chain_winner: string;
  anthropic_model: string;
  gemini_model: string;
  portkey_model: string;
  keys_set: { anthropic: boolean; portkey: boolean; gemini: boolean };
};

const mockLLMConfig: LLMConfig = {
  provider: "auto",
  auto_chain_winner: "fixture",
  anthropic_model: "claude-haiku-4-5",
  gemini_model: "gemini-2.5-flash-lite",
  portkey_model: "@vertexai/gemini-3.5-flash",
  keys_set: { anthropic: false, portkey: false, gemini: false }
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

  const response = await fetch(`${apiBaseUrl()}/api/batch/launch`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? "Failed to start batch");
  }
  return response.json();
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

  const response = await fetch(`${apiBaseUrl()}/api/batch/${batchId}`, {
    headers: authHeaders()
  });
  if (!response.ok) {
    throw new Error("Failed to load batch");
  }
  return response.json();
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

  const response = await fetch(`${apiBaseUrl()}/api/businesses${suffix}`, {
    headers: authHeaders()
  });
  if (!response.ok) {
    throw new Error("Failed to load businesses");
  }
  return response.json();
}

export async function shutdownBusiness(slug: string): Promise<Business> {
  if (useMockMode()) {
    throw new Error("Shutdown not available in mock mode");
  }

  const response = await fetch(`${apiBaseUrl()}/api/businesses/${slug}/shutdown`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() }
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? "Failed to shutdown business");
  }
  return response.json();
}

export async function getBacklog(limit = 10): Promise<BacklogResponse> {
  if (useMockMode()) {
    return { items: [], live_count: 0, max_concurrent_live: 5 };
  }

  const response = await fetch(
    `${apiBaseUrl()}/api/businesses/backlog?limit=${limit}`,
    { headers: authHeaders() }
  );
  if (!response.ok) {
    throw new Error("Failed to load backlog");
  }
  return response.json();
}

export async function getLLMConfig(): Promise<LLMConfig> {
  if (useMockMode()) {
    return mockLLMConfig;
  }

  const response = await fetch(`${apiBaseUrl()}/api/admin/llm`);
  if (!response.ok) {
    throw new Error("Failed to load LLM config");
  }
  return response.json();
}

export async function updateLLMConfig(
  patch: Partial<Pick<LLMConfig, "provider" | "anthropic_model" | "gemini_model" | "portkey_model">>
): Promise<LLMConfig> {
  if (useMockMode()) {
    return { ...mockLLMConfig, ...patch };
  }

  const response = await fetch(`${apiBaseUrl()}/api/admin/llm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch)
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? "Failed to update LLM config");
  }
  return response.json();
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
