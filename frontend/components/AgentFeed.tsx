import type { AgentEvent } from "@/lib/mock-data";
import styles from "./AgentFeed.module.css";

export function AgentFeed({ events }: { events: AgentEvent[] }) {
  return (
    <section className={styles.panel} aria-label="Agent event feed">
      <h2>Live Event Feed</h2>
      <div className={styles.feed}>
        {events.map((event) => (
          <article className={styles.event} key={`${event.agent_name}-${event.timestamp}`}>
            <div>
              <strong>{event.agent_name.replace("_", " ")}</strong>
              <span>{event.event_type.replace("_", " ")}</span>
            </div>
            <p>{event.message}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
