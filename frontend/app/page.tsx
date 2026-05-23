import Link from "next/link";

export default function HomePage() {
  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "64px 24px" }}>
      <h1 style={{ fontSize: 40, margin: 0 }}>Auto Ecommerce</h1>
      <p style={{ color: "#475569", fontSize: 18, lineHeight: 1.6 }}>
        AI-powered product testing with focused micro-stores and a live agent
        run dashboard.
      </p>
      <Link href="/dashboard">Open dashboard</Link>
    </main>
  );
}
