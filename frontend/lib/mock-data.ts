export type RunStatus = "started" | "running" | "completed" | "failed" | "fallback_completed";
export type AgentName = "research" | "buyer" | "legal_risk" | "advertising" | "score_launch" | "store_creator";
export type EventType = "pending" | "running" | "completed" | "failed" | "fallback_used";
export type Decision = "launch" | "no-launch";

export type LaunchRun = {
  run_id: string;
  temporal_workflow_id: string;
  product_name: string;
  slug: string;
  status: RunStatus;
  launch_score: number;
  decision: Decision;
  store_url: string;
  error: string | null;
};

export type AgentEvent = {
  agent_name: AgentName;
  event_type: EventType;
  message: string;
  timestamp: string;
  payload: Record<string, unknown>;
};

export type StoreConfig = {
  store_id: string;
  slug: string;
  store_url: string;
  product_name: string;
  tagline: string;
  description: string;
  price: number;
  hero_image_url: string;
  supplier: string;
  cta_text: string;
  shipping_note: string;
};

export type LaunchScoreBreakdown = {
  trend_score: number;
  margin_score: number;
  supplier_confidence: number;
  compliance_risk: number;
  launch_score: number;
  decision: Decision;
};

export const mockRunId = "7c0b5571-2f44-40ef-8c3f-3efca9b7e11f";

export const mockRun: LaunchRun = {
  run_id: mockRunId,
  temporal_workflow_id: `launch-store-${mockRunId}`,
  product_name: "Magnetic Phone Mount",
  slug: "magneticmount",
  status: "completed",
  launch_score: 0.615,
  decision: "launch",
  store_url: "https://magneticmount.fastaisolution.com",
  error: null
};

export const mockScore: LaunchScoreBreakdown = {
  trend_score: 0.86,
  margin_score: 0.72,
  supplier_confidence: 0.84,
  compliance_risk: 0.12,
  launch_score: 0.615,
  decision: "launch"
};

export const mockEvents: AgentEvent[] = [
  {
    agent_name: "research",
    event_type: "completed",
    message: "Research completed with trend score 0.86",
    timestamp: "2026-05-23T17:30:00Z",
    payload: { trend_score: 0.86, confidence: 0.82 }
  },
  {
    agent_name: "buyer",
    event_type: "completed",
    message: "Buyer found Demo Supplier 4821 with 0.84 confidence",
    timestamp: "2026-05-23T17:30:08Z",
    payload: { supplier_name: "Demo Supplier 4821", confidence_score: 0.84 }
  },
  {
    agent_name: "legal_risk",
    event_type: "completed",
    message: "Risk screen passed with low compliance risk",
    timestamp: "2026-05-23T17:30:15Z",
    payload: { risk_score: 0.12, cleared: true }
  },
  {
    agent_name: "advertising",
    event_type: "completed",
    message: "Advertising copy and hero prompt generated",
    timestamp: "2026-05-23T17:30:21Z",
    payload: { product_name: "MagSnap Pro" }
  },
  {
    agent_name: "score_launch",
    event_type: "completed",
    message: "Launch score 0.615 crossed launch threshold",
    timestamp: "2026-05-23T17:30:28Z",
    payload: { launch_score: 0.615, decision: "launch" }
  },
  {
    agent_name: "store_creator",
    event_type: "completed",
    message: "Store created at https://magneticmount.fastaisolution.com",
    timestamp: "2026-05-23T17:30:36Z",
    payload: { store_url: "https://magneticmount.fastaisolution.com" }
  }
];

export const mockStore: StoreConfig = {
  store_id: "14ddc76c-e9cc-42d3-a280-79d6f5a73b49",
  slug: "magneticmount",
  store_url: "https://magneticmount.fastaisolution.com",
  product_name: "MagSnap Pro",
  tagline: "Mount your phone in one clean snap.",
  description:
    "A compact magnetic phone mount built for fast one-handed docking and a cleaner dashboard.",
  price: 29.99,
  hero_image_url: "/demo/magnetic-phone-mount.png",
  supplier: "Demo Supplier 4821",
  cta_text: "Buy Now - Ships in 3 days",
  shipping_note: "Ships in 3 days"
};

export function getStoreBySlug(slug: string): StoreConfig | null {
  return slug === mockStore.slug ? mockStore : null;
}
