"use client";

import { useEffect, useMemo, useState } from "react";
import { AppNav } from "@/components/AppNav";
import {
  type BacklogResponse,
  type Business,
  type BusinessesResponse,
  getBacklog,
  getBusinesses,
  shutdownBusiness
} from "@/lib/api";
import styles from "./page.module.css";

type FilterStatus = "all" | "live" | "shutdown";
type SortKey = "launched_at" | "score" | "revenue" | "views" | "days_live";

function shortDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toISOString().slice(0, 10);
  } catch {
    return "—";
  }
}

function fmtMoney(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function fmtNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toLocaleString();
}

function fmtPct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

function displayStatus(b: Business): "live" | "shutdown" | "archived" {
  if (b.business_status === "live") return "live";
  if (b.business_status === "shutdown") return "shutdown";
  if (b.business_status === "archived") return "archived";
  // Backwards compat for runs that completed before the lifecycle migration
  // — anything with a store_url and decision=launch reads as "live" by default
  // until the operator (or future shutdown loop) flips it.
  if (b.decision === "launch" && b.store_url) return "live";
  return "archived";
}

export default function BusinessesPage() {
  const [data, setData] = useState<BusinessesResponse | null>(null);
  const [backlog, setBacklog] = useState<BacklogResponse | null>(null);
  const [filter, setFilter] = useState<FilterStatus>("all");
  const [sort, setSort] = useState<SortKey>("launched_at");
  const [error, setError] = useState<string | null>(null);
  const [busySlug, setBusySlug] = useState<string | null>(null);

  async function refresh() {
    try {
      const [b, bl] = await Promise.all([
        getBusinesses({ status: filter, sort }),
        getBacklog(8)
      ]);
      setData(b);
      setBacklog(bl);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load businesses");
    }
  }

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 5_000);
    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, sort]);

  async function handleShutdown(slug: string) {
    setBusySlug(slug);
    try {
      await shutdownBusiness(slug);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Shutdown failed");
    } finally {
      setBusySlug(null);
    }
  }

  const visibleBusinesses = useMemo(() => {
    if (!data) return [] as Business[];
    if (filter === "all") return data.businesses;
    return data.businesses.filter((b) => displayStatus(b) === filter);
  }, [data, filter]);

  const summary = data?.summary;

  return (
    <main className={styles.shell}>
      <AppNav />
      <header className={styles.header}>
        <div className={styles.brandLockup}>
          <span className={styles.statusDot} />
          BUSINESSES PORTFOLIO
          {summary && (
            <span className={styles.slotsBadge}>
              {summary.live_count}/{summary.max_concurrent_live} SLOTS
            </span>
          )}
        </div>
        <span className={styles.synthetic}>⚠ synthetic metrics</span>
      </header>

      {summary && (
        <div className={styles.statGrid}>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>LIVE</span>
            <span className={styles.statValue} data-tone="accent">
              {summary.live_count}
            </span>
            <span className={styles.statSub}>of {summary.max_concurrent_live} cap</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>TOTAL REVENUE</span>
            <span className={styles.statValue}>{fmtMoney(summary.total_revenue)}</span>
            <span className={styles.statSub}>synthetic · all-time</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>VIEWS / 24H</span>
            <span className={styles.statValue}>{fmtNum(summary.total_views_24h)}</span>
            <span className={styles.statSub}>synthetic</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>HIT RATE</span>
            <span className={styles.statValue} data-tone="warn">
              {fmtPct(summary.hit_rate)}
            </span>
            <span className={styles.statSub}>
              ≥ {summary.threshold.toFixed(2)} threshold
            </span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>LAUNCHED</span>
            <span className={styles.statValue}>{summary.total_launched}</span>
            <span className={styles.statSub}>all-time</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>BACKLOG</span>
            <span className={styles.statValue} data-tone="accent">
              {backlog?.items.length ?? 0}
            </span>
            <span className={styles.statSub}>queued ideas</span>
          </div>
        </div>
      )}

      {error && <p style={{ color: "var(--danger)", margin: "8px 0", fontFamily: "var(--mono)", fontSize: 12 }}>{error}</p>}

      <div className={styles.grid}>
        <div className={styles.primary}>
          <section className={styles.tableCard}>
            <div className={styles.tableHeader}>
              <span className={styles.cardTitle}>─ PORTFOLIO ─</span>
              <div style={{ display: "flex", gap: 6 }}>
                {(["all", "live", "shutdown"] as FilterStatus[]).map((f) => (
                  <button
                    key={f}
                    type="button"
                    className={styles.actionBtn}
                    data-active={filter === f}
                    onClick={() => setFilter(f)}
                    style={filter === f ? { borderColor: "var(--accent)", color: "var(--accent)" } : {}}
                  >
                    {f}
                  </button>
                ))}
                <select
                  className={styles.actionBtn}
                  value={sort}
                  onChange={(e) => setSort(e.target.value as SortKey)}
                  style={{ paddingRight: 12 }}
                >
                  <option value="launched_at">sort: launched</option>
                  <option value="score">sort: score</option>
                  <option value="revenue">sort: revenue</option>
                  <option value="views">sort: views</option>
                  <option value="days_live">sort: days live</option>
                </select>
              </div>
            </div>
            <div className={styles.tableScroll}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>STATUS</th>
                    <th>PRODUCT</th>
                    <th>LAUNCHED</th>
                    <th>SCORE</th>
                    <th>DAYS</th>
                    <th>VIEWS/24H</th>
                    <th>REV/24H</th>
                    <th>TOP SRC</th>
                    <th>ATTEMPT</th>
                    <th>ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleBusinesses.length === 0 && (
                    <tr>
                      <td colSpan={10} className={styles.emptyRow}>
                        no businesses match this filter
                      </td>
                    </tr>
                  )}
                  {visibleBusinesses.map((b) => {
                    const status = displayStatus(b);
                    const topSrc = b.top_sources[0];
                    return (
                      <tr key={b.run_id}>
                        <td>
                          <span className={styles.statusPill} data-status={status}>
                            ● {status}
                          </span>
                        </td>
                        <td>
                          <div className={styles.productCell}>
                            <span className={styles.productName}>{b.product_name}</span>
                            {b.store_url && (
                              <a className={styles.urlLink} href={b.store_url} target="_blank" rel="noreferrer noopener">
                                {b.store_url.replace(/^https?:\/\//, "")} ↗
                              </a>
                            )}
                          </div>
                        </td>
                        <td className={styles.numericCell}>{shortDate(b.launched_at)}</td>
                        <td className={styles.numericCell}>
                          <span className={styles.score}>{b.launch_score?.toFixed(3) ?? "—"}</span>
                        </td>
                        <td className={styles.numericCell}>{b.days_live?.toFixed(1) ?? "—"}</td>
                        <td className={styles.numericCell}>{fmtNum(b.views_24h)}</td>
                        <td className={styles.numericCell}>{fmtMoney(b.revenue_24h)}</td>
                        <td className={styles.numericCell}>
                          {topSrc ? `${topSrc.source} ${(topSrc.share * 100).toFixed(0)}%` : "—"}
                        </td>
                        <td className={styles.numericCell}>
                          {b.attempt_index ?? 1}
                        </td>
                        <td>
                          {status === "live" ? (
                            <button
                              type="button"
                              className={styles.actionBtn}
                              onClick={() => handleShutdown(b.slug)}
                              disabled={busySlug === b.slug}
                            >
                              {busySlug === b.slug ? "..." : "shutdown"}
                            </button>
                          ) : (
                            <span className={styles.productMeta}>{b.shutdown_reason || "—"}</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <aside className={styles.secondary}>
          <section className={styles.tableCard}>
            <div className={styles.tableHeader}>
              <span className={styles.cardTitle}>─ BACKLOG (TOP IDEAS) ─</span>
              <span className={styles.productMeta}>by trend_score</span>
            </div>
            <div className={styles.backlogList}>
              {(!backlog || backlog.items.length === 0) && (
                <p className={styles.empty}>no queued candidates — trigger a batch to populate</p>
              )}
              {backlog?.items.map((item) => (
                <div key={item.product_name} className={styles.backlogItem}>
                  <div>
                    <div className={styles.backlogProduct}>{item.product_name}</div>
                    <div className={styles.backlogMeta}>
                      {item.category || "—"} · {item.source || "—"}
                    </div>
                  </div>
                  <span className={styles.backlogScore}>{item.trend_score.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </section>

          <section className={styles.tableCard}>
            <div className={styles.tableHeader}>
              <span className={styles.cardTitle}>─ AUTONOMOUS LOOP ─</span>
              <span className={styles.productMeta}>(future)</span>
            </div>
            <p className={styles.productMeta} style={{ lineHeight: 1.5 }}>
              When live count drops below the cap, the top backlog item will be
              auto-promoted to a new slot. Underperforming stores will be
              auto-shut-down after a grace window. Surfaces are ready —
              loop ships next.
            </p>
          </section>
        </aside>
      </div>
    </main>
  );
}
