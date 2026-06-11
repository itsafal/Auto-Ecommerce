"use client";

import { useEffect, useState } from "react";
import { getHealth, type HealthSnapshot } from "@/lib/api";
import styles from "./LiveReadiness.module.css";

function toneFor(status: string): "ok" | "warn" | "muted" {
  if (["enabled", "configured", "live_ready", "receiving_events"].includes(status)) {
    return "ok";
  }
  if (["ready_no_events", "disabled", "not_configured", "needs_attention"].includes(status)) {
    return "warn";
  }
  return "muted";
}

function label(status: string): string {
  return status.replace(/_/g, " ");
}

export function LiveReadiness() {
  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const next = await getHealth();
        if (cancelled) return;
        setHealth(next);
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Health check failed");
        }
      }
    };

    load();
    const timer = window.setInterval(load, 10_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  if (error) {
    return (
      <section className={styles.card}>
        <div className={styles.header}>
          <span className={styles.title}>Live Readiness</span>
          <span className={styles.badge} data-tone="warn">unavailable</span>
        </div>
        <p className={styles.detail}>{error}</p>
      </section>
    );
  }

  if (!health) {
    return (
      <section className={styles.card}>
        <div className={styles.header}>
          <span className={styles.title}>Live Readiness</span>
          <span className={styles.badge} data-tone="muted">loading</span>
        </div>
      </section>
    );
  }

  const services = [
    ["DB", health.clickhouse.status, health.clickhouse.detail],
    ["Market", health.nimble.status, health.nimble.detail],
    ["LLM", health.llm.auto_chain_winner, health.llm.provider],
    ["Events", health.analytics.status, health.analytics.detail],
  ] as const;

  return (
    <section className={styles.card}>
      <div className={styles.header}>
        <span className={styles.title}>Live Readiness</span>
        <span className={styles.badge} data-tone={toneFor(health.readiness.status)}>
          {label(health.readiness.status)}
        </span>
      </div>

      <div className={styles.grid}>
        {services.map(([name, status, detail]) => (
          <div className={styles.service} key={name}>
            <span>{name}</span>
            <strong data-tone={toneFor(status)} title={detail}>
              {label(status)}
            </strong>
          </div>
        ))}
      </div>

      <div className={styles.runtime}>
        <span>batch {health.runtime.batch_target_count}</span>
        <span>threshold {health.runtime.launch_score_threshold.toFixed(2)}</span>
        <span>{health.runtime.demo_mode ? "demo mode" : "live mode"}</span>
      </div>

      {health.readiness.blockers.length > 0 && (
        <p className={styles.detail}>
          {health.readiness.blockers.slice(0, 2).join(" / ")}
        </p>
      )}
    </section>
  );
}
