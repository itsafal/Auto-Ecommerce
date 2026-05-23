import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import DashboardPage from "../app/dashboard/page";

describe("DashboardPage", () => {
  it("renders trigger button", () => {
    render(<DashboardPage />);
    expect(screen.getByRole("button", { name: /trigger agent run/i })).toBeInTheDocument();
  });

  it("clicking trigger creates visible run_id in mock mode", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    await user.click(screen.getByRole("button", { name: /trigger agent run/i }));

    await waitFor(() => {
      expect(screen.getByText("7c0b5571-2f44-40ef-8c3f-3efca9b7e11f")).toBeInTheDocument();
    });
    expect(screen.getByText("https://magneticmount.fastaisolution.com")).toBeInTheDocument();
  });

  it("agent timeline renders all five steps", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    await user.click(screen.getByRole("button", { name: /trigger agent run/i }));

    expect(await screen.findByText("Research")).toBeInTheDocument();
    expect(screen.getByText("Buyer")).toBeInTheDocument();
    expect(screen.getByText("Legal / Risk")).toBeInTheDocument();
    expect(screen.getByText("Advertising")).toBeInTheDocument();
    expect(screen.getByText("Store Creator")).toBeInTheDocument();
  });

  it("launch score renders all score components", () => {
    render(<DashboardPage />);

    expect(screen.getByText("Trend score")).toBeInTheDocument();
    expect(screen.getByText("Margin score")).toBeInTheDocument();
    expect(screen.getByText("Supplier confidence")).toBeInTheDocument();
    expect(screen.getByText("Compliance risk")).toBeInTheDocument();
    expect(screen.getByText(/final decision/i)).toBeInTheDocument();
  });
});
