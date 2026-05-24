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
