export type RunStatus = "started" | "running" | "completed" | "failed" | "fallback_completed";
export type AgentName = "research" | "buyer" | "legal_risk" | "advertising" | "score_launch" | "store_creator";
export type EventType = "pending" | "running" | "completed" | "failed" | "fallback_used";
export type Decision = "launch" | "pause";

// launch_score / decision / store_url are null while a run is in flight —
// the backend only fills them once the scoring agent completes.
export type LaunchRun = {
  run_id: string;
  temporal_workflow_id: string;
  product_name: string;
  slug: string;
  status: RunStatus;
  launch_score: number | null;
  decision: Decision | null;
  store_url: string | null;
  error: string | null;
};

export type AgentEvent = {
  agent_name: AgentName;
  event_type: EventType;
  message: string;
  timestamp: string;
  payload: Record<string, unknown>;
};

export type ProductVariant = {
  name: string;
  price: number;
  blurb: string;
  badge: string;
  accent: string;
};

export type FAQItem = { question: string; answer: string };
export type Review = { name: string; rating: number; text: string };

export type StoreTheme = {
  primary?: string;
  accent?: string;
  bg?: string;
  surface?: string;
  text?: string;
  text_muted?: string;
  border?: string;
  font_pair?: "serif-elegant" | "sans-modern" | "mono-tech";
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
  features?: string[];
  specs?: Record<string, string>;
  variants?: ProductVariant[];
  faq?: FAQItem[];
  reviews?: Review[];
  theme?: StoreTheme | null;
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
  store_url: "http://magneticmount.localhost:3000",
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
    message: "Store created at http://magneticmount.localhost:3000",
    timestamp: "2026-05-23T17:30:36Z",
    payload: { store_url: "http://magneticmount.localhost:3000" }
  }
];

export const mockStore: StoreConfig = {
  store_id: "14ddc76c-e9cc-42d3-a280-79d6f5a73b49",
  slug: "magneticmount",
  store_url: "http://magneticmount.localhost:3000",
  product_name: "MagSnap Pro",
  tagline: "Mount your phone in one clean snap.",
  description:
    "A compact magnetic phone mount built for fast one-handed docking and a cleaner dashboard.",
  price: 29.99,
  hero_image_url: "/demo/magnetic-phone-mount.png",
  supplier: "Demo Supplier 4821",
  cta_text: "Buy Now - Ships in 3 days",
  shipping_note: "Ships in 3 days · Tracked delivery",
  features: [
    "Strong N52 neodymium magnets - no slipping at highway speed",
    "Adhesive 3M VHB pad for dashboard, vent, or wall mounts",
    "Compatible with MagSafe and standard cases under 4mm",
    "Compact footprint, hides cleanly behind your phone",
    "30-day satisfaction guarantee, free returns"
  ],
  specs: {
    Material: "Aluminum + N52 neodymium",
    Compatibility: "MagSafe + ring adapter",
    "Mount type": "Dashboard / vent / wall",
    Weight: "38g",
    Warranty: "1 year limited"
  },
  variants: [
    { name: "MagSnap Standard", price: 29.99, blurb: "Single mount with 3M adhesive pad.", badge: "Most popular", accent: "#0f766e" },
    { name: "MagSnap Pro", price: 39.99, blurb: "Premium aluminum body, stronger magnet array.", badge: "Best build", accent: "#1d4ed8" },
    { name: "MagSnap Mini", price: 22.99, blurb: "Slimmer profile for compact dashboards.", badge: "Travel", accent: "#9333ea" },
    { name: "MagSnap Duo Bundle", price: 49.99, blurb: "Two mounts + ring adapter pack.", badge: "Save 18%", accent: "#b45309" }
  ],
  faq: [
    { question: "Will it hold a phone in a heavy case?", answer: "Yes, holds phones up to 250g including most rugged cases under 4mm thick." },
    { question: "How long does shipping take?", answer: "Orders ship in 3 days with full tracking." },
    { question: "Does it damage the dashboard?", answer: "3M VHB residue removes cleanly with isopropyl alcohol." }
  ],
  reviews: [
    { name: "Avery K.", rating: 5.0, text: "Holds rock solid on rough roads. Best mount I've owned." },
    { name: "Jordan M.", rating: 4.5, text: "Sleek and tiny. Magnet is way stronger than expected." },
    { name: "Priya S.", rating: 5.0, text: "Set up in 30 seconds, working perfectly two months in." }
  ]
};

export function getStoreBySlug(slug: string): StoreConfig | null {
  return slug === mockStore.slug ? mockStore : null;
}
