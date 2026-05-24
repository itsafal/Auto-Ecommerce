import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from "../app/dashboard/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard"
}));

describe("DashboardPage", () => {
  it("renders the autonomous deploy button (no human product selection)", () => {
    render(<DashboardPage />);
    // Manual single-product trigger was removed; only the autonomous
    // batch deploy button should be present.
    expect(
      screen.getByRole("button", { name: /deploy autonomous batch/i })
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /trigger agent run/i })).toBeNull();
  });

  it("renders the operator console banner + nav tabs", () => {
    render(<DashboardPage />);
    expect(screen.getByText(/AUTO-ECOMMERCE/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /businesses/i })).toBeInTheDocument();
  });

  it("agent timeline renders all six pipeline steps in their pending state", () => {
    render(<DashboardPage />);
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("Buyer")).toBeInTheDocument();
    expect(screen.getByText("Legal / Risk")).toBeInTheDocument();
    expect(screen.getByText("Advertising")).toBeInTheDocument();
    expect(screen.getByText("Score Launch")).toBeInTheDocument();
    expect(screen.getByText("Store Creator")).toBeInTheDocument();
  });

  it("launch score panel renders all score components", () => {
    render(<DashboardPage />);
    expect(screen.getByText("Trend score")).toBeInTheDocument();
    expect(screen.getByText("Margin score")).toBeInTheDocument();
    expect(screen.getByText("Supplier confidence")).toBeInTheDocument();
    expect(screen.getByText("Compliance risk")).toBeInTheDocument();
    expect(screen.getByText(/final decision/i)).toBeInTheDocument();
  });
});
