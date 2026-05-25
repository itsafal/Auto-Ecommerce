"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { type BatchRun, type BatchStatusResponse, getBatch, triggerBatch } from "@/lib/api";
import styles from "./BatchPanel.module.css";

type SlotStatus = "pending" | "running" | "approved" | "rejected";

/** Plan 04: a slot only shows "rejected" when the safety cap was hit
 *  (errors starting with "exhausted_" or "trending_pool_exhausted"). A
 *  terminal-but-not-approved attempt mid-slot is just the inter-product
 *  swap — the slot is still working, so we report "running". */
function isExhaustionError(err: string | null | undefined): boolean {
  if (!err) return false;
  return err.startsWith("exhausted_") || err.startsWith("trending_pool_exhausted");
}

function slotStatus(run: BatchRun | undefined, threshold: number): SlotStatus {
  if (!run) return "pending";
  const terminal = ["completed", "failed", "fallback_completed"].includes(run.status);
  if (!terminal) return "running";
  const approved =
    run.launch_score != null && run.launch_score >= threshold && run.decision === "launch";
  if (approved) return "approved";
  // Terminal and not approved → only "rejected" if the safety cap fired.
  // Otherwise the slot is between products and will spin up another pipeline.
  return isExhaustionError(run.error) ? "rejected" : "running";
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
  /** Notified whenever the focused slot's run_id changes — either because the
   *  auto-picker landed on a new "most interesting" slot, or because the user
   *  manually clicked a slot card. The dashboard wires this to its agent
   *  pipeline, event feed, and launch score panels. */
  onActiveRunChange?: (runId: string | null) => void;
  /** Notified on every batch poll so the dashboard can render the batch
   *  timeline (live + failed slot outcomes). */
  onBatchChange?: (batch: BatchStatusResponse | null) => void;
  /** Externally-controlled focus override (e.g. user clicked a timeline row).
   *  When set, this run is highlighted as the active slot regardless of the
   *  auto-picker. */
  selectedRunId?: string | null;
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

export function BatchPanel({
  onActiveRunChange,
  onBatchChange,
  selectedRunId,
}: BatchPanelProps = {}) {
  const [batch, setBatch] = useState<BatchStatusResponse | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const lastFocusRef = useRef<string | null>(null);
  // Manual slot selection (set by clicking a slot card). When non-null, this
  // wins over the auto-picker so the user's choice persists across polls.
  const [manualRunId, setManualRunId] = useState<string | null>(null);

  // Push batch updates upstream for the dashboard's BatchTimeline.
  useEffect(() => {
    onBatchChange?.(batch);
  }, [batch, onBatchChange]);

  // If the dashboard externally sets a selectedRunId (e.g. user clicked a
  // timeline row), adopt it as the manual selection.
  useEffect(() => {
    if (selectedRunId !== undefined && selectedRunId !== manualRunId) {
      setManualRunId(selectedRunId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRunId]);

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

  // Manual selection wins over the auto-picker. Validate the manualRunId is
  // still present in the current batch; if a stale id (from a prior batch)
  // is supplied, fall through to the auto-picker.
  const focusRunId = useMemo(() => {
    if (manualRunId && batch?.runs.some((r) => String(r.run_id) === manualRunId)) {
      return manualRunId;
    }
    return pickFocusRunId(batch);
  }, [batch, manualRunId]);

  useEffect(() => {
    if (focusRunId !== lastFocusRef.current) {
      lastFocusRef.current = focusRunId;
      onActiveRunChange?.(focusRunId);
    }
  }, [focusRunId, onActiveRunChange]);

  // When a new batch starts (id changes), drop the manual selection so the
  // auto-picker takes over from scratch.
  useEffect(() => {
    setManualRunId(null);
  }, [batch?.batch_id]);

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
            : "5 stores · score ≥ 0.65 · 2 tries/product · slot keeps trying"}
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
          {slots.map(({ slot, run, status }) => {
            const slotRunId = run ? String(run.run_id) : null;
            const isSelected = slotRunId !== null && slotRunId === focusRunId;
            const clickable = slotRunId !== null;
            return (
            <article
              key={slot}
              className={styles.slot}
              data-status={status}
              data-selected={isSelected ? "true" : undefined}
              data-clickable={clickable ? "true" : undefined}
              role={clickable ? "button" : undefined}
              tabIndex={clickable ? 0 : undefined}
              onClick={() => {
                if (slotRunId) setManualRunId(slotRunId);
              }}
              onKeyDown={(e) => {
                if (clickable && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault();
                  if (slotRunId) setManualRunId(slotRunId);
                }
              }}
              title={clickable ? "Click to view this slot's score breakdown" : undefined}
            >
              <div className={styles.slotHeader}>
                <span className={styles.slotIndex}>SLOT {String(slot + 1).padStart(2, "0")}</span>
                <span className={styles.statusPill} data-status={status}>
                  {status}
                </span>
              </div>
              <p className={styles.product}>{run?.product_name ?? "—"}</p>
              <div className={styles.meta}>
                <span>
                  try<strong>{run?.product_attempt ?? 1}</strong>
                </span>
                <span>
                  product<strong>{run?.products_tried ?? 1}</strong>
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
                <span
                  className={styles.placeholder}
                  title={status === "rejected" ? (run?.error ?? "safety cap reached") : undefined}
                >
                  {status === "running"
                    ? "running pipeline..."
                    : status === "rejected"
                      ? `exhausted (${run?.products_tried ?? 0} products tried)`
                      : "queued"}
                </span>
              )}
            </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
