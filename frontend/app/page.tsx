import Link from "next/link";
import styles from "./home.module.css";

const PIPELINE_STEPS = [
  "research",
  "buyer",
  "legal",
  "advertising",
  "theme",
  "score",
  "store"
];

export default function HomePage() {
  return (
    <main className={`console ${styles.shell}`}>
      <section className={styles.panel}>
        <p className={styles.lockup}>
          <span className={styles.statusDot} />
          <span className={styles.lockupText}>AUTO-ECOMMERCE ● SYSTEM ONLINE</span>
          <span className="blink" aria-hidden="true" />
        </p>
        <h1 className={styles.headline}>
          Autonomous storefronts,
          <br />
          end to end.
        </h1>
        <p className={styles.copy}>
          AI agents discover trending products, ground them in live market
          data, score the opportunity, and deploy themed micro-stores — five
          slots in parallel, no human in the loop.
        </p>
        <nav className={styles.actions}>
          <Link className={styles.primaryAction} href="/dashboard">
            ▶ Open dashboard
          </Link>
          <Link className={styles.secondaryAction} href="/login">
            Log in
          </Link>
          <Link className={styles.secondaryAction} href="/signup">
            Create account
          </Link>
        </nav>
        <p className={styles.pipeline} data-panel>
          <strong>pipeline</strong>
          {PIPELINE_STEPS.map((step, i) => (
            <span key={step} className={styles.step} style={{ "--i": i } as React.CSSProperties}>
              {i > 0 && <span className={styles.arrow}>→</span>}
              {step}
            </span>
          ))}
        </p>
      </section>
    </main>
  );
}
