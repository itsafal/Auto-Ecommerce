import type { AgentEvent } from "@/lib/mock-data";
import styles from "./AgentFeed.module.css";

const agentLabels: Record<string, string> = {
  research: "Research",
  buyer: "Buyer",
  legal_risk: "Legal / Risk",
  advertising: "Advertising",
  score_launch: "Score Launch",
  store_creator: "Store Creator"
};

function formatTime(timestamp: string): string {
  try {
    return new Date(timestamp).toLocaleTimeString();
  } catch {
    return timestamp;
  }
}

export function AgentFeed({ events }: { events: AgentEvent[] }) {
  const ordered = [...events].sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1));

  return (
    <section className={styles.panel} aria-label="Agent event feed">
      <div className={styles.header}>
        <h2>Live Event Feed</h2>
        <span className={styles.count}>{events.length} events</span>
      </div>
      <div className={styles.feed}>
        {ordered.length === 0 ? (
          <p className={styles.empty}>Trigger an agent run to see live events appear here.</p>
        ) : (
          ordered.map((event) => (
            <article
              className={styles.event}
              data-status={event.event_type}
              key={`${event.agent_name}-${event.event_type}-${event.timestamp}`}
            >
              <div className={styles.eventHeader}>
                <strong>{agentLabels[event.agent_name] ?? event.agent_name.replace("_", " ")}</strong>
                <span className={styles.status} data-status={event.event_type}>
                  {event.event_type.replace("_", " ")}
                </span>
              </div>
              <p>{event.message}</p>
              <time className={styles.time}>{formatTime(event.timestamp)}</time>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
