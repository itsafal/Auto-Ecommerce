"use client";

import { useEffect, useMemo, useState } from "react";
import { AppNav } from "@/components/AppNav";
import {
  type BacklogResponse,
  type Business,
  type BusinessesResponse,
  type CategoryStat,
  type LifecycleTickResult,
  type PortfolioExperiments,
  type ShutdownCandidate,
  getBacklog,
  getBusinesses,
  getCategoryLeaderboard,
  getLifecycleCandidates,
  getPortfolioExperiments,
  runLifecycleTick,
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

function metricsLabel(source: BusinessesResponse["data_source"] | undefined): string {
  if (source === "events") return "event metrics";
  if (source === "mixed") return "mixed metrics";
  if (source === "insufficient_data" || source === "none") return "insufficient data";
  return "synthetic metrics";
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

function tickSummary(result: LifecycleTickResult): string {
  const parts = [`${result.shutdowns.length} shut down`];
  parts.push(
    result.promotion
      ? `promoted "${result.promotion.slots[0]?.product_name ?? "backlog item"}"`
      : "nothing promoted"
  );
  parts.push(`${result.live_count}/${result.max_concurrent_live} live`);
  return parts.join(" · ");
}

export default function BusinessesPage() {
  const [data, setData] = useState<BusinessesResponse | null>(null);
  const [backlog, setBacklog] = useState<BacklogResponse | null>(null);
  const [candidates, setCandidates] = useState<ShutdownCandidate[]>([]);
  const [categories, setCategories] = useState<CategoryStat[]>([]);
  const [experiments, setExperiments] = useState<PortfolioExperiments | null>(null);
  const [filter, setFilter] = useState<FilterStatus>("all");
  const [sort, setSort] = useState<SortKey>("launched_at");
  const [error, setError] = useState<string | null>(null);
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [isTicking, setIsTicking] = useState(false);
  const [tickResult, setTickResult] = useState<string | null>(null);

  async function refresh() {
    try {
      const [b, bl, lc, cats, exp] = await Promise.all([
        getBusinesses({ status: filter, sort }),
        getBacklog(8),
        getLifecycleCandidates(),
        getCategoryLeaderboard(),
        getPortfolioExperiments()
      ]);
      setData(b);
      setBacklog(bl);
      setCandidates(lc.shutdown_candidates);
      setCategories(cats);
      setExperiments(exp);
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

  async function handleLifecycleTick() {
    setIsTicking(true);
    setTickResult(null);
    try {
      const result = await runLifecycleTick();
      setTickResult(tickSummary(result));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lifecycle tick failed");
    } finally {
      setIsTicking(false);
    }
  }

  const visibleBusinesses = useMemo(() => {
    if (!data) return [] as Business[];
    if (filter === "all") return data.businesses;
    return data.businesses.filter((b) => displayStatus(b) === filter);
  }, [data, filter]);

  const summary = data?.summary;

  return (
    <main className={`console ${styles.shell}`}>
      <AppNav />
      <header className={styles.header} data-boot="1">
        <div className={styles.brandLockup}>
          <span className={styles.statusDot} />
          BUSINESSES PORTFOLIO
          {summary && (
            <span className={styles.slotsBadge}>
              {summary.live_count}/{summary.max_concurrent_live} SLOTS
            </span>
          )}
        </div>
        <span className={styles.synthetic} data-source={data?.data_source ?? "synthetic"}>
          {metricsLabel(data?.data_source)}
        </span>
      </header>

      {summary && (
        <div className={styles.statGrid} data-boot="2">
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
            <span className={styles.statSub}>{metricsLabel(data?.data_source)} · all-time</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>VIEWS / 24H</span>
            <span className={styles.statValue}>{fmtNum(summary.total_views_24h)}</span>
            <span className={styles.statSub}>{metricsLabel(data?.data_source)}</span>
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

      {error && <p className={styles.errorBanner}>{error}</p>}

      <div className={styles.grid} data-boot="3">
        <div className={styles.primary}>
          <section className={styles.tableCard} data-panel>
            <div className={styles.tableHeader}>
              <span className={styles.cardTitle}>─ PORTFOLIO ─</span>
              <div className={styles.filters}>
                {(["all", "live", "shutdown"] as FilterStatus[]).map((f) => (
                  <button
                    key={f}
                    type="button"
                    className={styles.actionBtn}
                    data-active={filter === f}
                    onClick={() => setFilter(f)}
                  >
                    {f}
                  </button>
                ))}
                <select
                  className={styles.sortSelect}
                  value={sort}
                  onChange={(e) => setSort(e.target.value as SortKey)}
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
                    <th>METRICS</th>
                    <th>ATTEMPT</th>
                    <th>ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleBusinesses.length === 0 && (
                    <tr>
                      <td colSpan={11} className={styles.emptyRow}>
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
                          <span className={styles.metricBadge} data-source={b.metric_source}>
                            {b.metric_source}
                          </span>
                        </td>
                        <td className={styles.numericCell}>
                          {b.attempt_index ?? 1}
                        </td>
                        <td>
                          {status === "live" ? (
                            <button
                              type="button"
                              className={styles.actionBtn}
                              data-tone="danger"
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

          <section className={styles.tableCard} data-panel>
            <div className={styles.tableHeader}>
              <span className={styles.cardTitle}>─ STORE FUNNEL ─</span>
              <span className={styles.productMeta}>views → cta → capture → purchase</span>
            </div>
            <div className={styles.tableScroll}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>PRODUCT</th>
                    <th>VIEWS</th>
                    <th>CTA</th>
                    <th>EMAIL</th>
                    <th>CHECKOUT</th>
                    <th>PURCHASE</th>
                    <th>CTA RATE</th>
                    <th>CAPTURE</th>
                    <th>PURCHASE RATE</th>
                    <th>SIGNAL</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleBusinesses.length === 0 && (
                    <tr>
                      <td colSpan={10} className={styles.emptyRow}>
                        no funnel data for this filter
                      </td>
                    </tr>
                  )}
                  {visibleBusinesses.map((b) => (
                    <tr key={`${b.run_id}-funnel`}>
                      <td>
                        <span className={styles.productName}>{b.product_name}</span>
                      </td>
                      <td className={styles.numericCell}>{fmtNum(b.funnel.views)}</td>
                      <td className={styles.numericCell}>{fmtNum(b.funnel.cta_clicks)}</td>
                      <td className={styles.numericCell}>{fmtNum(b.funnel.email_captures)}</td>
                      <td className={styles.numericCell}>{fmtNum(b.funnel.checkouts)}</td>
                      <td className={styles.numericCell}>{fmtNum(b.funnel.purchase_attempts)}</td>
                      <td className={styles.numericCell}>
                        <span className={styles.score}>{fmtPct(b.funnel.cta_rate)}</span>
                      </td>
                      <td className={styles.numericCell}>{fmtPct(b.funnel.capture_rate)}</td>
                      <td className={styles.numericCell}>
                        <span className={styles.score}>{fmtPct(b.funnel.purchase_rate)}</span>
                      </td>
                      <td className={styles.numericCell}>
                        <span className={styles.metricBadge} data-source={b.metric_source}>
                          {b.metric_source}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className={styles.tableCard} data-panel>
            <div className={styles.tableHeader}>
              <span className={styles.cardTitle}>─ CATEGORY INTEL ─</span>
              <span className={styles.productMeta}>hit rate · avg score</span>
            </div>
            {categories.length === 0 ? (
              <p className={styles.empty}>no launched businesses to analyze yet</p>
            ) : (
              <div className={styles.tableScroll}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>CATEGORY</th>
                      <th>LIVE</th>
                      <th>SHUTDOWN</th>
                      <th>HIT RATE</th>
                      <th>AVG SCORE</th>
                      <th>TOP PRODUCT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {categories.map((c) => (
                      <tr key={c.category}>
                        <td className={styles.productName}>{c.category}</td>
                        <td className={styles.numericCell}>{c.live}</td>
                        <td className={styles.numericCell}>{c.shutdown}</td>
                        <td className={styles.numericCell}>
                          <span className={styles.score}>{fmtPct(c.hit_rate)}</span>
                        </td>
                        <td className={styles.numericCell}>{c.avg_launch_score.toFixed(3)}</td>
                        <td className={styles.productMeta}>{c.top_product}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        <aside className={styles.secondary}>
          <section className={styles.tableCard} data-panel>
            <div className={styles.tableHeader}>
              <span className={styles.cardTitle}>─ AUTONOMOUS LOOP ─</span>
              <button
                type="button"
                className={styles.tickBtn}
                onClick={handleLifecycleTick}
                disabled={isTicking}
              >
                {isTicking ? "running..." : "▶ run tick"}
              </button>
            </div>
            <p className={styles.loopNote}>
              One tick shuts down live businesses that miss the revenue and
              conversion targets, then promotes the top backlog item into any
              open slot.
            </p>
            {tickResult && <p className={styles.tickResult}>{tickResult}</p>}
            <div className={styles.backlogList}>
              {candidates.length === 0 ? (
                <p className={styles.empty}>no shutdown candidates — portfolio healthy</p>
              ) : (
                candidates.map((c, i) => (
                  <div key={`${c.slug}-${i}`} className={styles.backlogItem} data-tone="danger">
                    <div>
                      <div className={styles.backlogProduct}>{c.product_name}</div>
                      <div className={styles.backlogMeta}>
                        {c.reason} · {c.days_live.toFixed(1)}d live
                      </div>
                    </div>
                    <span className={styles.candidateRevenue}>{fmtMoney(c.revenue_24h)}/24h</span>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className={styles.tableCard} data-panel>
            <div className={styles.tableHeader}>
              <span className={styles.cardTitle}>─ AD EXPERIMENTS ─</span>
              <span className={styles.productMeta}>
                {experiments
                  ? `${experiments.experiment_count} plans · ${fmtMoney(experiments.total_daily_budget)}/day`
                  : "—"}
              </span>
            </div>
            <div className={styles.backlogList}>
              {(!experiments || experiments.plans.length === 0) && (
                <p className={styles.empty}>no live businesses — experiment plans appear per live store</p>
              )}
              {experiments?.plans.map((plan) => (
                <div key={plan.run_id} className={styles.backlogItem}>
                  <div>
                    <div className={styles.backlogProduct}>{plan.product_name}</div>
                    <div className={styles.backlogMeta}>
                      {plan.channels
                        .map((ch) => `${ch.channel} ${fmtMoney(ch.budget)}`)
                        .join(" · ")}
                    </div>
                  </div>
                  <span className={styles.backlogScore}>{fmtMoney(plan.daily_budget)}</span>
                </div>
              ))}
            </div>
          </section>

          <section className={styles.tableCard} data-panel>
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
        </aside>
      </div>
    </main>
  );
}
