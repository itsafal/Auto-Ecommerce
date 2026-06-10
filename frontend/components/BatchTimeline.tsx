"use client";

import type { BatchRun, BatchStatusResponse } from "@/lib/api";
import styles from "./BatchTimeline.module.css";

type TimelineKind = "live" | "failed";

type TimelineEntry = {
  run: BatchRun;
  kind: TimelineKind;
};

function isExhaustionError(err: string | null | undefined): boolean {
  if (!err) return false;
  return err.startsWith("exhausted_") || err.startsWith("trending_pool_exhausted");
}

/** A run is "terminal" for timeline purposes when:
 *   - it landed live (decision=launch + store_url), or
 *   - the slot was exhausted by the safety cap.
 *  Intermediate rejects on the way to a slot's next product are NOT terminal
 *  — they're transient state and shouldn't clutter the timeline. */
function classifyForTimeline(run: BatchRun, threshold: number): TimelineKind | null {
  const approved =
    run.launch_score != null && run.launch_score >= threshold && run.decision === "launch";
  if (approved && run.store_url) return "live";
  if (run.status === "failed" && isExhaustionError(run.error)) return "failed";
  return null;
}

function fmtScore(s: number | null | undefined): string {
  if (s == null) return "—";
  return s.toFixed(3);
}

type Props = {
  batch: BatchStatusResponse | null;
  /** Currently focused run in the dashboard (highlighted in timeline). */
  selectedRunId?: string | null;
  /** Click handler — clicking a timeline row focuses that run in the
   *  Launch Score breakdown + event feed. */
  onSelectRun?: (runId: string) => void;
};

export function BatchTimeline({ batch, selectedRunId, onSelectRun }: Props) {
  const threshold = batch?.threshold ?? 0.55;
  // Backend returns runs in completion order; preserve that ordering and
  // filter down to terminal outcomes (live or safety-cap-failed).
  const entries: TimelineEntry[] = (batch?.runs ?? [])
    .map((run) => {
      const kind = classifyForTimeline(run, threshold);
      if (kind == null) return null;
      return { run, kind } as TimelineEntry;
    })
    .filter((e): e is TimelineEntry => e !== null);

  return (
    <section className={styles.card}>
      <h2 className={styles.title}>BATCH TIMELINE</h2>
      {entries.length === 0 ? (
        <p className={styles.empty}>
          {batch
            ? "No outcomes yet — slots are still running."
            : "Trigger a batch to see live and failed stores here as they land."}
        </p>
      ) : (
        <ol className={styles.list}>
          {entries.map((entry, idx) => {
            const r = entry.run;
            const isSelected = selectedRunId === String(r.run_id);
            const slotLabel = `S${String((r.batch_slot ?? 0) + 1).padStart(2, "0")}`;
            return (
              <li key={`${r.run_id}-${idx}`} className={styles.row} data-kind={entry.kind}>
                <button
                  type="button"
                  className={styles.rowButton}
                  data-selected={isSelected ? "true" : undefined}
                  onClick={() => onSelectRun?.(String(r.run_id))}
                  title={isSelected ? "Selected" : "View score breakdown"}
                >
                  <span className={styles.marker} data-kind={entry.kind} aria-hidden="true">
                    {entry.kind === "live" ? "●" : "✕"}
                  </span>
                  <div className={styles.body}>
                    <div className={styles.headRow}>
                      <span className={styles.slotTag}>{slotLabel}</span>
                      <span className={styles.product}>{r.product_name}</span>
                      <span className={styles.score} data-kind={entry.kind}>
                        {fmtScore(r.launch_score)}
                      </span>
                    </div>
                    {entry.kind === "live" && r.store_url ? (
                      <a
                        className={styles.link}
                        href={r.store_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {r.store_url.replace(/^https?:\/\//, "")} ↗
                      </a>
                    ) : (
                      <span className={styles.failedNote} title={r.error ?? undefined}>
                        {r.error?.startsWith("trending_pool")
                          ? "trending pool exhausted"
                          : `exhausted after ${r.products_tried ?? "?"} products`}
                      </span>
                    )}
                  </div>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
