"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./AppNav.module.css";

const TABS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/businesses", label: "Businesses" }
];

export function AppNav() {
  const pathname = usePathname() ?? "/";
  return (
    <nav className={styles.nav}>
      {TABS.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          className={styles.tab}
          data-active={pathname.startsWith(t.href)}
        >
          {t.label}
        </Link>
      ))}
      <span className={styles.spacer} />
      <span className={styles.right}>operator console</span>
    </nav>
  );
}
