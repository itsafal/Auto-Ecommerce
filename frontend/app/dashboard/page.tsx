"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AgentFeed } from "@/components/AgentFeed";
import { AgentTimeline } from "@/components/AgentTimeline";
import { LaunchScore } from "@/components/LaunchScore";
import {
  getCurrentUser,
  getRun,
  getRunEvents,
  getTrendingProducts,
  triggerAgentRun,
  useMockMode
} from "@/lib/api";
import { type AgentEvent, type LaunchRun, mockEvents, mockRun, mockScore } from "@/lib/mock-data";
import styles from "./page.module.css";

const fallbackProducts = [
  "Magnetic Phone Mount",
  "Portable Power Station",
  "Red Light Therapy Mask",
  "Mini Portable Projector",
  "Smart Ring Fitness Tracker",
  "Portable Ice Bath",
  "Smart Desk Lamp",
  "Ergo Keyboard",
  "Portable Blender"
];

export default function DashboardPage() {
  const router = useRouter();
  const [productName, setProductName] = useState("Magnetic Phone Mount");
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<LaunchRun | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isTriggering, setIsTriggering] = useState(false);
  const [trendingProducts, setTrendingProducts] = useState<string[]>(fallbackProducts);
  const [trendingSource, setTrendingSource] = useState<string>("fixture");
  const [isLoadingTrends, setIsLoadingTrends] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSessionReady, setIsSessionReady] = useState(useMockMode);

  const score = useMemo(() => {
    if (!run) {
      return mockScore;
    }
    return {
      ...mockScore,
      launch_score: run.launch_score ?? mockScore.launch_score,
      decision: run.decision ?? mockScore.decision
    };
  }, [run]);

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

  async function refreshTrends() {
    setIsLoadingTrends(true);
    try {
      const res = await getTrendingProducts();
      if (res.products.length > 0) {
        setTrendingProducts(res.products);
        setTrendingSource(res.source);
        if (!res.products.includes(productName)) {
          setProductName(res.products[0]);
        }
      }
    } catch {
      // keep fallback list silently
    } finally {
      setIsLoadingTrends(false);
    }
  }

  useEffect(() => {
    refreshTrends();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleTrigger() {
    setIsTriggering(true);
    setError(null);
    setEvents([]);
    setRun(null);
    try {
      const response = await triggerAgentRun(productName);
      setRunId(response.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger agent run");
    } finally {
      setIsTriggering(false);
    }
  }

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
      <main className={styles.shell}>
        <p className={styles.eyebrow}>Operator dashboard</p>
        <h1>Checking session</h1>
      </main>
    );
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Operator dashboard</p>
          <h1>Live Agent Run</h1>
        </div>
        {visibleRun.store_url ? (
          <a href={visibleRun.store_url} className={styles.storeLink}>
            {visibleRun.store_url.replace(/^https?:\/\//, "")}
          </a>
        ) : (
          <span className={styles.storeLink}>pending...</span>
        )}
      </header>

      <section className={styles.controlPanel}>
        <label>
          Product to test
          <input
            list="demo-products"
            value={productName}
            onChange={(event) => setProductName(event.target.value)}
          />
          <div className={styles.trendHeader}>
            <span className={styles.trendLabel}>
              Trend Scout {trendingSource === "gemini" ? "· live (Gemini)" : "· fixture"}
            </span>
            <button
              type="button"
              className={styles.trendRefresh}
              onClick={refreshTrends}
              disabled={isLoadingTrends || isTriggering}
            >
              {isLoadingTrends ? "Scanning..." : "Refresh trends"}
            </button>
          </div>
          <div className={styles.chips}>
            {trendingProducts.map((product) => (
              <button
                type="button"
                key={product}
                className={styles.chip}
                data-active={product === productName}
                onClick={() => setProductName(product)}
                disabled={isTriggering}
              >
                {product}
              </button>
            ))}
          </div>
          <datalist id="demo-products">
            {trendingProducts.map((product) => (
              <option key={product} value={product} />
            ))}
          </datalist>
        </label>
        <button onClick={handleTrigger} disabled={isTriggering}>
          {isTriggering ? "Starting..." : "Trigger Agent Run"}
        </button>
      </section>

      {error ? <p className={styles.error}>{error}</p> : null}

      <section className={styles.runStrip}>
        <div>
          <span>run_id</span>
          <strong>{runId ?? "No run yet"}</strong>
        </div>
        <div>
          <span>Status</span>
          <strong>{runId ? visibleRun.status : "waiting"}</strong>
        </div>
        <div>
          <span>Decision</span>
          <strong>{runId ? visibleRun.decision : "pending"}</strong>
        </div>
      </section>

      <div className={styles.grid}>
        <div className={styles.primary}>
          <AgentTimeline events={visibleEvents} />
          <AgentFeed events={visibleEvents} />
        </div>
        <aside className={styles.secondary}>
          <LaunchScore score={score} />
          <section className={styles.finalUrl}>
            <h2>Final Store URL</h2>
            {visibleRun.store_url ? (
              <a href={visibleRun.store_url}>{visibleRun.store_url}</a>
            ) : (
              <p>Provisioning storefront...</p>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}
