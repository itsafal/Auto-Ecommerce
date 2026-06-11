"use client";

import { useEffect, useMemo, useState, type CSSProperties, type FormEvent } from "react";
import { trackStorefrontEvent, type StorefrontEventType } from "@/lib/api";
import type { StoreConfig, StoreTheme } from "@/lib/mock-data";
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

// Theme tokens are projected onto the `.shell` root as CSS custom properties.
// Every color in StoreTemplate.module.css reads `var(--name, <default>)`, so
// missing tokens silently fall through to the original teal palette.
function themeStyle(theme?: StoreTheme | null): CSSProperties {
  if (!theme) return {};
  const vars: Record<string, string> = {};
  if (theme.primary) vars["--accent"] = theme.primary;
  if (theme.accent) vars["--accent-hover"] = theme.accent;
  if (theme.bg) vars["--bg"] = theme.bg;
  if (theme.surface) vars["--surface"] = theme.surface;
  if (theme.text) vars["--text"] = theme.text;
  if (theme.text_muted) vars["--text-muted"] = theme.text_muted;
  if (theme.border) vars["--border"] = theme.border;
  return vars as CSSProperties;
}

function isRealImageUrl(url: string | undefined | null): boolean {
  if (!url) return false;
  return url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:");
}

function sessionId(): string {
  const key = "auto_ecommerce_store_session";
  try {
    const existing = window.localStorage.getItem(key);
    if (existing) return existing;
    const next = window.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
    window.localStorage.setItem(key, next);
    return next;
  } catch {
    return `${Date.now()}-${Math.random()}`;
  }
}

function trafficSource(): string {
  try {
    const params = new URLSearchParams(window.location.search);
    const utm = params.get("utm_source");
    if (utm) return utm.slice(0, 80);
    const referrer = document.referrer.toLowerCase();
    for (const source of ["google", "tiktok", "instagram", "reddit", "email"]) {
      if (referrer.includes(source)) return source;
    }
  } catch {
    return "direct";
  }
  return "direct";
}

export function StoreTemplate({ store }: { store: StoreConfig }) {
  const [email, setEmail] = useState("");
  const [checkoutStatus, setCheckoutStatus] = useState("");
  const variants = store.variants ?? [];
  const features = store.features ?? [];
  const specs = store.specs ?? {};
  const faq = store.faq ?? [];
  const reviews = store.reviews ?? [];
  const domain = store.store_url.replace(/^https?:\/\//, "");
  const accent = store.theme?.primary ?? "#0f766e";
  const showRealHero = isRealImageUrl(store.hero_image_url);
  const sid = useMemo(() => (typeof window === "undefined" ? "" : sessionId()), []);

  const track = (eventType: StorefrontEventType, metadata: Record<string, unknown> = {}) => {
    if (!sid) return;
    void trackStorefrontEvent(store.slug, {
      event_type: eventType,
      session_id: sid,
      source: trafficSource(),
      value: eventType === "purchase_attempt" ? store.price : 0,
      metadata: {
        product_name: store.product_name,
        price: store.price,
        ...metadata,
      },
    }).catch(() => {
      // Analytics should never block a public storefront interaction.
    });
  };

  useEffect(() => {
    track("view_product", { path: window.location.pathname });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store.slug]);

  function handleCtaClick(location: string) {
    track("click_cta", { location });
  }

  function handleCheckoutSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    track("email_capture", { email_domain: email.split("@")[1] ?? "" });
    track("purchase_attempt", { location: "checkout", has_email: Boolean(email) });
    setCheckoutStatus("Saved. We'll send availability and checkout details.");
  }

  return (
    <main
      className={styles.shell}
      style={themeStyle(store.theme)}
      data-font-pair={store.theme?.font_pair ?? "sans-modern"}
    >
      <nav className={styles.topbar}>
        <span className={styles.brand}>{store.product_name}</span>
        <span className={styles.domain}>{domain}</span>
        <a href="#checkout" className={styles.navCta} onClick={() => handleCtaClick("nav")}>
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
            <a className={styles.cta} href="#checkout" onClick={() => handleCtaClick("hero")}>
              {store.cta_text}
            </a>
          </div>
          <p className={styles.supplier}>Supplier: {store.supplier}</p>
        </div>
        <div className={styles.productVisual} aria-label={`${store.product_name} visual`}>
          {showRealHero ? (
            <img
              className={styles.heroImage}
              src={store.hero_image_url}
              alt={store.product_name}
            />
          ) : (
            <div className={styles.device}>
              <div className={styles.mount} />
              <div className={styles.phone} />
            </div>
          )}
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
                style={{ borderTopColor: v.accent || accent }}
              >
                {v.badge && (
                  <span className={styles.variantBadge} style={{ background: v.accent || accent }}>
                    {v.badge}
                  </span>
                )}
                <h3>{v.name}</h3>
                <p className={styles.variantBlurb}>{v.blurb}</p>
                <div className={styles.variantFoot}>
                  <span className={styles.variantPrice}>${v.price.toFixed(2)}</span>
                  <a
                    href="#checkout"
                    className={styles.variantCta}
                    style={{ background: v.accent || accent }}
                    onClick={() => handleCtaClick(`variant:${v.name}`)}
                  >
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
        <form className={styles.checkoutForm} onSubmit={handleCheckoutSubmit}>
          <input
            type="email"
            required
            value={email}
            placeholder="you@example.com"
            aria-label="Email address"
            onChange={(event) => setEmail(event.target.value)}
          />
          <button className={styles.cta} type="submit">
            {store.cta_text}
          </button>
        </form>
        {checkoutStatus && <p className={styles.checkoutStatus}>{checkoutStatus}</p>}
        <p className={styles.legal}>
          {domain} · 30-day returns · Tracked shipping · Supplier: {store.supplier}
        </p>
      </footer>
    </main>
  );
}
