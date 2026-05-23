import type { StoreConfig } from "@/lib/mock-data";
import styles from "./StoreTemplate.module.css";

export function StoreTemplate({ store }: { store: StoreConfig }) {
  return (
    <main className={styles.shell}>
      <section className={styles.hero}>
        <div className={styles.copy}>
          <p className={styles.domain}>{store.store_url.replace("https://", "")}</p>
          <h1>{store.product_name}</h1>
          <p className={styles.tagline}>{store.tagline}</p>
          <p className={styles.description}>{store.description}</p>
          <div className={styles.purchaseRow}>
            <span className={styles.price}>${store.price.toFixed(2)}</span>
            <a className={styles.cta} href="#checkout">
              {store.cta_text}
            </a>
          </div>
          <p className={styles.supplier}>
            Supplier: {store.supplier} · {store.shipping_note}
          </p>
        </div>
        <div className={styles.productVisual} aria-label={`${store.product_name} product visual`}>
          <div className={styles.device}>
            <div className={styles.mount} />
            <div className={styles.phone} />
          </div>
        </div>
      </section>
    </main>
  );
}
