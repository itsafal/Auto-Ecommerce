import type { AgentEvent, AgentName, EventType } from "@/lib/mock-data";
import styles from "./AgentTimeline.module.css";

const steps: Array<{ agent: AgentName; label: string }> = [
  { agent: "research", label: "Research" },
  { agent: "buyer", label: "Buyer" },
  { agent: "legal_risk", label: "Legal / Risk" },
  { agent: "advertising", label: "Advertising" },
  { agent: "score_launch", label: "Score Launch" },
  { agent: "store_creator", label: "Store Creator" }
];

const statusLabels: Record<EventType | "pending", string> = {
  pending: "pending",
  running: "running",
  completed: "completed",
  failed: "failed",
  fallback_used: "fallback used"
};

export function getStepStatus(agent: AgentName, events: AgentEvent[]): EventType | "pending" {
  const event = [...events].reverse().find((item) => item.agent_name === agent);
  return event?.event_type ?? "pending";
}

export function AgentTimeline({ events }: { events: AgentEvent[] }) {
  const completedCount = steps.filter(
    (step) => getStepStatus(step.agent, events) === "completed"
  ).length;
  const progressPct = Math.round((completedCount / steps.length) * 100);

  return (
    <section className={styles.panel} aria-label="Agent timeline">
      <div className={styles.header}>
        <h2>Agent Pipeline</h2>
        <span>
          {completedCount}/{steps.length} agents · {events.length} events
        </span>
      </div>
      <div className={styles.progressBar} role="progressbar" aria-valuenow={progressPct}>
        <div className={styles.progressFill} style={{ width: `${progressPct}%` }} />
      </div>
      <div className={styles.timeline}>
        {steps.map((step) => {
          const status = getStepStatus(step.agent, events);
          return (
            <div className={styles.step} data-status={status} key={step.agent}>
              <span className={styles.dot} />
              <span className={styles.name}>{step.label}</span>
              <span className={styles.status}>{statusLabels[status]}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
