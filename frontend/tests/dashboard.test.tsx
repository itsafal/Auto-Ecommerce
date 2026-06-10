import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from "../app/dashboard/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard"
}));

async function renderDashboard() {
  render(<DashboardPage />);
  await screen.findByText("Agent Model");
}

describe("DashboardPage", () => {
  it("renders the autonomous batch deploy button", async () => {
    await renderDashboard();
    expect(
      screen.getByRole("button", { name: /deploy autonomous batch/i })
    ).toBeInTheDocument();
  });

  it("clicking deploy renders the batch slot grid in mock mode", async () => {
    const user = userEvent.setup();
    await renderDashboard();

    await user.click(screen.getByRole("button", { name: /deploy autonomous batch/i }));

    expect(await screen.findByText("SLOT 01")).toBeInTheDocument();
    expect(screen.getByText("SLOT 05")).toBeInTheDocument();
  });

  it("agent timeline renders all pipeline steps", async () => {
    await renderDashboard();

    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("Buyer")).toBeInTheDocument();
    expect(screen.getByText("Legal / Risk")).toBeInTheDocument();
    expect(screen.getByText("Advertising")).toBeInTheDocument();
    expect(screen.getByText("Score Launch")).toBeInTheDocument();
    expect(screen.getByText("Store Creator")).toBeInTheDocument();
  });

  it("launch score renders all score components", async () => {
    await renderDashboard();

    expect(screen.getByText("Trend score")).toBeInTheDocument();
    expect(screen.getByText("Margin score")).toBeInTheDocument();
    expect(screen.getByText("Supplier confidence")).toBeInTheDocument();
    expect(screen.getByText("Compliance risk")).toBeInTheDocument();
    expect(screen.getByText(/final decision/i)).toBeInTheDocument();
  });
});
