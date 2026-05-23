import type { LaunchScoreBreakdown } from "@/lib/mock-data";
import styles from "./LaunchScore.module.css";

const formatScore = (value: number | null | undefined) =>
  value == null ? "—" : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");

export function LaunchScore({ score }: { score: LaunchScoreBreakdown }) {
  const rows = [
    ["Trend score", score.trend_score],
    ["Margin score", score.margin_score],
    ["Supplier confidence", score.supplier_confidence],
    ["Compliance risk", score.compliance_risk]
  ] as const;

  return (
    <section className={styles.panel} aria-label="Launch score">
      <div className={styles.header}>
        <div>
          <h2>Launch Score</h2>
          <p>Final decision: {score.decision ?? "pending"}</p>
        </div>
        <strong>{formatScore(score.launch_score)}</strong>
      </div>
      <div className={styles.rows}>
        {rows.map(([label, value]) => (
          <div className={styles.row} key={label}>
            <span>{label}</span>
            <span>{formatScore(value)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
