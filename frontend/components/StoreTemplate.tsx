import type { StoreConfig } from "@/lib/mock-data";
import styles from "./StoreTemplate.module.css";

function Stars({ rating }: { rating: number }) {
  const full = Math.round(rating);
  return (
    <span className={styles.stars} aria-label={`${rating} out of 5`}>
      {"★".repeat(full)}
      {"☆".repeat(Math.max(0, 5 - full))}
    </span>
  );
}

export function StoreTemplate({ store }: { store: StoreConfig }) {
  const variants = store.variants ?? [];
  const features = store.features ?? [];
  const specs = store.specs ?? {};
  const faq = store.faq ?? [];
  const reviews = store.reviews ?? [];
  const domain = store.store_url.replace(/^https?:\/\//, "");

  return (
    <main className={styles.shell}>
      <nav className={styles.topbar}>
        <span className={styles.brand}>{store.product_name}</span>
        <span className={styles.domain}>{domain}</span>
        <a href="#checkout" className={styles.navCta}>
          {store.cta_text}
        </a>
      </nav>

      <section className={styles.hero}>
        <div className={styles.copy}>
          <p className={styles.eyebrow}>{store.shipping_note}</p>
          <h1>{store.product_name}</h1>
          <p className={styles.tagline}>{store.tagline}</p>
          <p className={styles.description}>{store.description}</p>
          <div className={styles.purchaseRow}>
            <span className={styles.price}>${store.price.toFixed(2)}</span>
            <a className={styles.cta} href="#checkout">
              {store.cta_text}
            </a>
          </div>
          <p className={styles.supplier}>Supplier: {store.supplier}</p>
        </div>
        <div className={styles.productVisual} aria-label={`${store.product_name} visual`}>
          <div className={styles.device}>
            <div className={styles.mount} />
            <div className={styles.phone} />
          </div>
        </div>
      </section>

      {features.length > 0 && (
        <section className={styles.section}>
          <h2>Why people love it</h2>
          <ul className={styles.features}>
            {features.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </section>
      )}

      {variants.length > 0 && (
        <section className={styles.section}>
          <h2>Choose your pack</h2>
          <div className={styles.variantGrid}>
            {variants.map((v) => (
              <article
                className={styles.variantCard}
                key={v.name}
                style={{ borderTopColor: v.accent || "#0f766e" }}
              >
                {v.badge && (
                  <span className={styles.variantBadge} style={{ background: v.accent || "#0f766e" }}>
                    {v.badge}
                  </span>
                )}
                <h3>{v.name}</h3>
                <p className={styles.variantBlurb}>{v.blurb}</p>
                <div className={styles.variantFoot}>
                  <span className={styles.variantPrice}>${v.price.toFixed(2)}</span>
                  <a href="#checkout" className={styles.variantCta} style={{ background: v.accent || "#0f766e" }}>
                    Add to cart
                  </a>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {Object.keys(specs).length > 0 && (
        <section className={styles.section}>
          <h2>Specs</h2>
          <div className={styles.specGrid}>
            {Object.entries(specs).map(([k, v]) => (
              <div className={styles.specRow} key={k}>
                <span className={styles.specKey}>{k}</span>
                <span className={styles.specValue}>{v}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {reviews.length > 0 && (
        <section className={styles.section}>
          <h2>What customers say</h2>
          <div className={styles.reviewGrid}>
            {reviews.map((r) => (
              <article className={styles.reviewCard} key={r.name + r.text.slice(0, 12)}>
                <Stars rating={r.rating} />
                <p>{r.text}</p>
                <span className={styles.reviewer}>— {r.name}</span>
              </article>
            ))}
          </div>
        </section>
      )}

      {faq.length > 0 && (
        <section className={styles.section}>
          <h2>Frequently asked</h2>
          <div className={styles.faqList}>
            {faq.map((item) => (
              <details className={styles.faqItem} key={item.question}>
                <summary>{item.question}</summary>
                <p>{item.answer}</p>
              </details>
            ))}
          </div>
        </section>
      )}

      <footer className={styles.footer} id="checkout">
        <h2>Ready to launch into your life?</h2>
        <a className={styles.cta} href="#">{store.cta_text}</a>
        <p className={styles.legal}>
          {domain} · 30-day returns · Tracked shipping · Supplier: {store.supplier}
        </p>
      </footer>
    </main>
  );
}
