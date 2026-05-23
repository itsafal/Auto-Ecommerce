import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StoreTemplate } from "../components/StoreTemplate";
import { mockStore } from "../lib/mock-data";

describe("StoreTemplate", () => {
  it("store template renders product config", () => {
    render(<StoreTemplate store={mockStore} />);

    expect(screen.getByRole("heading", { name: "MagSnap Pro" })).toBeInTheDocument();
    expect(screen.getByText("Mount your phone in one clean snap.")).toBeInTheDocument();
    expect(screen.getByText("$29.99")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Buy Now - Ships in 3 days" })).toBeInTheDocument();
    expect(screen.getByText(/Supplier: Demo Supplier 4821/)).toBeInTheDocument();
  });
});
