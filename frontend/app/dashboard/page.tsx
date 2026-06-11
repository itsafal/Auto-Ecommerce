"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AgentFeed } from "@/components/AgentFeed";
import { AgentTimeline } from "@/components/AgentTimeline";
import { AppNav } from "@/components/AppNav";
import { BatchPanel } from "@/components/BatchPanel";
import { BatchTimeline } from "@/components/BatchTimeline";
import { LaunchScore } from "@/components/LaunchScore";
import { LiveReadiness } from "@/components/LiveReadiness";
import { ModelPicker } from "@/components/ModelPicker";
import {
  type BatchStatusResponse,
  getCurrentUser,
  getRun,
  getRunEvents,
  useMockMode,
} from "@/lib/api";
import { type AgentEvent, type LaunchRun, mockEvents, mockRun, mockScore } from "@/lib/mock-data";
import styles from "./page.module.css";

function formatLatency(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function shortRunId(id: string | null): string {
  if (!id) return "—";
  return id.split("-")[0] + "…";
}

export default function DashboardPage() {
  const router = useRouter();
  // runId is driven by BatchPanel via onActiveRunChange — the dashboard no
  // longer triggers a single product run itself; the read-only detail panels
  // (run strip, agent pipeline, event feed, launch score, final URL) follow
  // whichever slot in the latest batch is currently most interesting.
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<LaunchRun | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSessionReady, setIsSessionReady] = useState(useMockMode);
  // Latest batch snapshot (forwarded from BatchPanel) — drives the timeline.
  const [batch, setBatch] = useState<BatchStatusResponse | null>(null);
  // User-clicked focus override (from a slot card or timeline row).
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const score = useMemo(() => {
    if (!run && events.length === 0) {
      return mockScore;
    }
    const findPayload = (agent: string, type: "running" | "completed" = "completed") =>
      [...events].reverse().find(
        (e) => e.agent_name === agent && e.event_type === type
      )?.payload as Record<string, unknown> | undefined;

    const research = findPayload("research");
    const buyer = findPayload("buyer");
    const legal = findPayload("legal_risk");

    const num = (v: unknown, fallback: number): number =>
      typeof v === "number" ? v : fallback;

    return {
      ...mockScore,
      trend_score: num(research?.trend_score, mockScore.trend_score),
      margin_score: num(buyer?.margin_score, mockScore.margin_score),
      supplier_confidence: num(buyer?.supplier_confidence, mockScore.supplier_confidence),
      compliance_risk: num(legal?.risk_score, mockScore.compliance_risk),
      launch_score: run?.launch_score ?? mockScore.launch_score,
      decision: run?.decision ?? mockScore.decision
    };
  }, [run, events]);

  /** Run wall-clock latency = (last event timestamp) - (first event timestamp). */
  const runLatencyMs = useMemo<number | null>(() => {
    if (events.length < 2) return null;
    const stamps = events
      .map((e) => new Date(e.timestamp).getTime())
      .filter((n) => Number.isFinite(n) && n > 0);
    if (stamps.length < 2) return null;
    return Math.max(...stamps) - Math.min(...stamps);
  }, [events]);

  useEffect(() => {
    if (useMockMode()) {
      return;
    }

    const token = window.localStorage.getItem("auto_ecommerce_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    getCurrentUser(token)
      .then(() => setIsSessionReady(true))
      .catch(() => {
        window.localStorage.removeItem("auto_ecommerce_token");
        window.localStorage.removeItem("auto_ecommerce_user");
        router.replace("/login");
      });
  }, [router]);

  // Whenever the focused runId changes (set by BatchPanel as slots progress),
  // reset the local run+events so the detail panels show clean state while
  // we re-poll the freshly-focused slot.
  useEffect(() => {
    setRun(null);
    setEvents([]);
  }, [runId]);

  useEffect(() => {
    if (!runId) {
      return;
    }

    const terminalStatuses = new Set(["completed", "failed", "fallback_completed"]);
    let cancelled = false;

    const tick = async () => {
      try {
        const [nextRun, nextEvents] = await Promise.all([getRun(runId), getRunEvents(runId)]);
        if (cancelled) return;
        setRun(nextRun);
        setEvents(nextEvents.events);
        if (terminalStatuses.has(nextRun.status)) {
          window.clearInterval(timer);
        }
      } catch {
        if (!cancelled) {
          setError("Polling failed. Retrying with latest known run state.");
        }
      }
    };

    const timer = window.setInterval(tick, 800);
    tick();

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [runId]);

  const visibleRun = run ?? mockRun;
  const visibleEvents = events.length > 0 ? events : mockEvents.slice(0, runId ? mockEvents.length : 0);

  if (!isSessionReady) {
    return (
      <main className={`console ${styles.shell}`}>
        <p className={styles.eyebrow}>Operator dashboard</p>
        <h1>Checking session</h1>
      </main>
    );
  }

  const displayStatus = runId ? visibleRun.status : "waiting";
  const displayDecision = runId ? (visibleRun.decision || "pending") : "pending";
  const displayScore = runId && visibleRun.launch_score != null
    ? visibleRun.launch_score.toFixed(3)
    : "—";
  const decisionState =
    displayDecision === "launch" ? "ok"
    : displayDecision === "pause" ? "warn"
    : "muted";

  return (
    <main className={`console ${styles.shell}`}>
      <AppNav />
      <header className={styles.header} data-boot="1">
        <div className={styles.brandLockup}>
          <span className={styles.statusDot} />
          AUTO-ECOMMERCE
          <span className={styles.statusText}>● ONLINE</span>
          <span className="blink" aria-hidden="true" />
        </div>
        {runId && run?.store_url ? (
          <a href={run.store_url} className={styles.storeLink}>
            {run.store_url.replace(/^https?:\/\//, "")}
          </a>
        ) : (
          <span className={styles.storeLink} data-pending="true">
            {runId ? "store: provisioning" : "no run yet"}
          </span>
        )}
      </header>

      <section className={styles.controlPanel} data-panel data-boot="2">
        <ModelPicker />
        <LiveReadiness />
      </section>

      <BatchPanel
        onActiveRunChange={setRunId}
        onBatchChange={setBatch}
        selectedRunId={selectedRunId}
      />

      {error ? <p className={styles.error}>{error}</p> : null}

      <section className={styles.runStrip} data-boot="4">
        <div>
          <span>RUN_ID</span>
          <strong title={runId ?? "No run yet"}>{shortRunId(runId)}</strong>
        </div>
        <div>
          <span>STATUS</span>
          <strong data-state={runId && visibleRun.status?.includes("completed") ? "ok" : "muted"}>
            {displayStatus}
          </strong>
        </div>
        <div>
          <span>DECISION</span>
          <strong data-state={decisionState}>{displayDecision}</strong>
        </div>
        <div>
          <span>SCORE</span>
          <strong data-state={displayScore !== "—" ? "warn" : "muted"}>{displayScore}</strong>
        </div>
        <div>
          <span>LATENCY</span>
          <strong data-state="muted">{formatLatency(runLatencyMs)}</strong>
        </div>
      </section>

      <div className={styles.grid} data-boot="5">
        <div className={styles.primary}>
          <AgentTimeline events={visibleEvents} />
          <AgentFeed events={visibleEvents} />
        </div>
        <aside className={styles.secondary}>
          <LaunchScore score={score} />
          <BatchTimeline
            batch={batch}
            selectedRunId={runId}
            onSelectRun={setSelectedRunId}
          />
        </aside>
      </div>
    </main>
  );
}
