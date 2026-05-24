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
};

export type BatchStatusResponse = {
  batch_id: string;
  target_count: number;
  threshold: number;
  runs: BatchRun[];
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
  business_status: string;
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

export async function getBusinesses(params?: {
  status?: "live" | "shutdown" | "all";
  sort?: "launched_at" | "score" | "revenue" | "views" | "days_live";
}): Promise<BusinessesResponse> {
  if (useMockMode()) {
    return {
      data_source: "synthetic",
      summary: {
        live_count: 2,
        max_concurrent_live: 5,
        total_launched: 3,
        total_revenue: 1234.56,
        total_views_24h: 480,
        hit_rate: 0.66,
        threshold: 0.65
      },
      businesses: []
    };
  }
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.sort) qs.set("sort", params.sort);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  const response = await fetch(`${apiBaseUrl()}/api/businesses${query}`);
  if (!response.ok) throw new Error("Failed to load businesses");
  return response.json();
}

export async function shutdownBusiness(slug: string): Promise<Business> {
  if (useMockMode()) {
    throw new Error("Shutdown disabled in mock mode");
  }
  const response = await fetch(`${apiBaseUrl()}/api/businesses/${encodeURIComponent(slug)}/shutdown`, {
    method: "POST"
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Failed to shut down business");
  }
  return response.json();
}

export async function getBacklog(limit = 10): Promise<BacklogResponse> {
  if (useMockMode()) {
    return { items: [], live_count: 0, max_concurrent_live: 5 };
  }
  const response = await fetch(`${apiBaseUrl()}/api/businesses/backlog?limit=${limit}`);
  if (!response.ok) throw new Error("Failed to load backlog");
  return response.json();
}

export async function triggerBatch(payload: {
  count: number;
  threshold?: number;
  products?: string[];
}): Promise<BatchTriggerResponse> {
  if (useMockMode()) {
    // Mock: a synthetic batch with N slots already approved.
    return {
      batch_id: "mock-batch-0001",
      target_count: payload.count,
      threshold: payload.threshold ?? 0.65,
      slots: Array.from({ length: payload.count }).map((_, i) => ({
        slot: i,
        run_id: `${mockRunId}-${i}`,
        product_name: ["Magnetic Phone Mount", "Ergo Keyboard", "Portable Blender", "Mini Projector", "Smart Ring"][i] ?? `Mock Product ${i}`
      }))
    };
  }
  const response = await fetch(`${apiBaseUrl()}/api/batch/launch`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Failed to start batch");
  }
  return response.json();
}

export async function getBatch(batchId: string): Promise<BatchStatusResponse> {
  if (useMockMode()) {
    return {
      batch_id: batchId,
      target_count: 3,
      threshold: 0.65,
      runs: [
        { ...mockRun, batch_id: batchId, batch_slot: 0, attempt_index: 1 } as BatchRun,
        { ...mockRun, run_id: `${mockRunId}-1`, batch_id: batchId, batch_slot: 1, attempt_index: 1, store_url: "http://ergokeyboard.localhost:3000" } as BatchRun,
        { ...mockRun, run_id: `${mockRunId}-2`, batch_id: batchId, batch_slot: 2, attempt_index: 1, store_url: "http://portableblender.localhost:3000" } as BatchRun
      ]
    };
  }
  const response = await fetch(`${apiBaseUrl()}/api/batch/${batchId}`);
  if (!response.ok) {
    throw new Error("Failed to load batch status");
  }
  return response.json();
}

export async function getLLMConfig(): Promise<LLMConfig> {
  const response = await fetch(`${apiBaseUrl()}/api/admin/llm`);
  if (!response.ok) {
    throw new Error("Failed to load LLM config");
  }
  return response.json();
}

export async function updateLLMConfig(
  patch: Partial<Pick<LLMConfig, "provider" | "anthropic_model" | "gemini_model" | "portkey_model">>
): Promise<LLMConfig> {
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
