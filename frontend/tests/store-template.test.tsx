import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StoreTemplate } from "../components/StoreTemplate";
import { mockStore } from "../lib/mock-data";

describe("StoreTemplate", () => {
  it("store template renders product config", () => {
    render(<StoreTemplate store={mockStore} />);

    expect(screen.getByRole("heading", { level: 1, name: "MagSnap Pro" })).toBeInTheDocument();
    expect(screen.getByText("Mount your phone in one clean snap.")).toBeInTheDocument();
    expect(screen.getAllByText("$29.99").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Buy Now - Ships in 3 days" }).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Supplier: Demo Supplier 4821/).length).toBeGreaterThan(0);
    // richer storefront sections
    expect(screen.getByRole("heading", { name: /Choose your pack/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Frequently asked/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /What customers say/i })).toBeInTheDocument();
    expect(screen.getByText(/MagSnap Duo Bundle/)).toBeInTheDocument();
  });
});
