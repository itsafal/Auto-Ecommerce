"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { type BatchRun, type BatchStatusResponse, getBatch, triggerBatch } from "@/lib/api";
import styles from "./BatchPanel.module.css";

type SlotStatus = "pending" | "running" | "approved" | "rejected";

function slotStatus(run: BatchRun | undefined, threshold: number): SlotStatus {
  if (!run) return "pending";
  const terminal = ["completed", "failed", "fallback_completed"].includes(run.status);
  if (!terminal) return "running";
  const approved =
    run.launch_score != null && run.launch_score >= threshold && run.decision === "launch";
  return approved ? "approved" : "rejected";
}

/** Group the flat list of runs by slot, keeping only the most recent attempt per slot. */
function latestPerSlot(runs: BatchRun[]): Map<number, BatchRun> {
  const map = new Map<number, BatchRun>();
  for (const r of runs) {
    const s = r.batch_slot ?? -1;
    if (s < 0) continue;
    const prev = map.get(s);
    if (!prev || r.attempt_index >= prev.attempt_index) {
      map.set(s, r);
    }
  }
  return map;
}

function shortRun(id: string): string {
  return id.split("-")[0] + "…";
}

/** Pick the most-interesting attempt the operator should be watching: first
 *  in-progress slot, falling back to the most recently terminal attempt. */
function pickFocusRunId(batch: BatchStatusResponse | null): string | null {
  if (!batch || batch.runs.length === 0) return null;
  const map = latestPerSlot(batch.runs);
  const ordered = Array.from(map.values()).sort(
    (a, b) => (a.batch_slot ?? 0) - (b.batch_slot ?? 0)
  );
  const running = ordered.find((r) => slotStatus(r, batch.threshold) === "running");
  if (running) return String(running.run_id);
  // No running slot → return the most recently-updated attempt across all rows.
  const sortedByAttempt = [...batch.runs].sort(
    (a, b) => (b.attempt_index ?? 0) - (a.attempt_index ?? 0)
  );
  return sortedByAttempt[0] ? String(sortedByAttempt[0].run_id) : null;
}

type BatchPanelProps = {
  /** Notified whenever the "currently most interesting" slot's run_id changes,
   *  so the parent dashboard can wire its live agent panels to the active slot. */
  onActiveRunChange?: (runId: string | null) => void;
};

/** localStorage key that persists the active batch_id across page navigations
 *  so visiting /businesses and coming back doesn't lose the in-flight batch. */
const ACTIVE_BATCH_KEY = "auto_ecommerce_active_batch_id";

function readStoredBatchId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(ACTIVE_BATCH_KEY);
  } catch {
    return null;
  }
}

function writeStoredBatchId(id: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (id) window.localStorage.setItem(ACTIVE_BATCH_KEY, id);
    else window.localStorage.removeItem(ACTIVE_BATCH_KEY);
  } catch {
    // ignore — localStorage can be blocked (private mode etc.)
  }
}

export function BatchPanel({ onActiveRunChange }: BatchPanelProps = {}) {
  const [batch, setBatch] = useState<BatchStatusResponse | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const lastFocusRef = useRef<string | null>(null);

  // On mount, restore the last active batch_id (if any) so navigation to
  // /businesses and back keeps the in-progress slot cards visible instead of
  // showing an empty panel while the backend is still running.
  useEffect(() => {
    const stored = readStoredBatchId();
    if (!stored) return;
    let cancelled = false;
    getBatch(stored)
      .then((next) => {
        if (cancelled) return;
        setBatch(next);
      })
      .catch(() => {
        // Stale batch id (probably from a server restart). Clear it.
        writeStoredBatchId(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Whenever the batch state changes, notify the parent of the active runId.
  useEffect(() => {
    const focus = pickFocusRunId(batch);
    if (focus !== lastFocusRef.current) {
      lastFocusRef.current = focus;
      onActiveRunChange?.(focus);
    }
  }, [batch, onActiveRunChange]);

  // Poll the batch while at least one slot is still running.
  useEffect(() => {
    if (!batch) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const next = await getBatch(batch.batch_id);
        if (cancelled) return;
        setBatch(next);
        const slots = latestPerSlot(next.runs);
        const stillRunning = Array.from(slots.values()).some(
          (r) => slotStatus(r, next.threshold) === "running"
        );
        if (!stillRunning && slots.size >= next.target_count) {
          if (pollTimerRef.current) {
            window.clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }
        }
      } catch {
        // Soft-fail; keep showing last known state.
      }
    };

    pollTimerRef.current = window.setInterval(tick, 1200);
    tick();

    return () => {
      cancelled = true;
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [batch?.batch_id, batch?.target_count]);

  async function handleDeploy() {
    setIsTriggering(true);
    setError(null);
    try {
      // No knobs in the autonomous UI — backend defaults from settings
      // (BATCH_TARGET_COUNT=5, LAUNCH_SCORE_THRESHOLD=0.65) drive everything.
      const response = await triggerBatch({ count: 5 });
      // Persist so the panel survives a Dashboard ↔ Businesses round-trip.
      writeStoredBatchId(response.batch_id);
      // Seed the local state with a placeholder so the slot cards render
      // immediately while we wait for the first poll.
      setBatch({
        batch_id: response.batch_id,
        target_count: response.target_count,
        threshold: response.threshold,
        runs: response.slots.map((s) => ({
          run_id: s.run_id,
          temporal_workflow_id: `launch-store-${s.run_id}`,
          product_name: s.product_name,
          slug: s.product_name.toLowerCase().replace(/[^a-z0-9]/g, ""),
          status: "started",
          launch_score: null,
          decision: null,
          store_url: null,
          error: null,
          batch_id: response.batch_id,
          batch_slot: s.slot,
          attempt_index: 1
        }))
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start batch");
    } finally {
      setIsTriggering(false);
    }
  }

  const slots = useMemo(() => {
    if (!batch) return [];
    const map = latestPerSlot(batch.runs);
    const out: Array<{ slot: number; run: BatchRun | undefined; status: SlotStatus }> = [];
    for (let i = 0; i < batch.target_count; i++) {
      const run = map.get(i);
      out.push({ slot: i, run, status: slotStatus(run, batch.threshold) });
    }
    return out;
  }, [batch]);

  const approved = slots.filter((s) => s.status === "approved").length;

  return (
    <section className={styles.card}>
      <div className={styles.header}>
        <span className={styles.title}>─ AUTONOMOUS BATCH DEPLOY ─</span>
        <span className={styles.subtitle}>
          {batch
            ? `batch_id ${shortRun(batch.batch_id)} · ${approved}/${batch.target_count} approved`
            : "5 stores · score ≥ 0.65 · no humans · dedup window 7d"}
        </span>
      </div>

      <div className={styles.autonomousRow}>
        <p className={styles.autonomousNote}>
          Trend Scout discovers fresh products, scores them, deploys the ones
          that clear the launch threshold. Already-tried products are skipped
          for the next 7 days.
        </p>
        <button
          type="button"
          className={styles.deployButton}
          onClick={handleDeploy}
          disabled={isTriggering}
        >
          {isTriggering ? "Starting..." : "▶ Deploy autonomous batch"}
        </button>
      </div>

      {error ? <p className={styles.error}>{error}</p> : null}

      {batch && slots.length > 0 && (
        <div className={styles.grid}>
          {slots.map(({ slot, run, status }) => (
            <article key={slot} className={styles.slot} data-status={status}>
              <div className={styles.slotHeader}>
                <span className={styles.slotIndex}>SLOT {String(slot + 1).padStart(2, "0")}</span>
                <span className={styles.statusPill} data-status={status}>
                  {status}
                </span>
              </div>
              <p className={styles.product}>{run?.product_name ?? "—"}</p>
              <div className={styles.meta}>
                <span>
                  attempt<strong>{run?.attempt_index ?? 1}</strong>
                </span>
                <span>
                  score
                  <strong>{run?.launch_score != null ? run.launch_score.toFixed(3) : "—"}</strong>
                </span>
              </div>
              {run?.store_url && status === "approved" ? (
                <a
                  className={styles.url}
                  href={run.store_url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  {run.store_url.replace(/^https?:\/\//, "")}
                </a>
              ) : (
                <span className={styles.placeholder}>
                  {status === "running" ? "running pipeline..." : status === "rejected" ? "below threshold" : "queued"}
                </span>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
