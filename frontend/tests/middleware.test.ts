import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { extractSubdomainSlug } from "../middleware";
import { middleware } from "../middleware";

describe("extractSubdomainSlug", () => {
  it("middleware extracts subdomain slug", () => {
    expect(extractSubdomainSlug("magneticmount.fastaisolution.com")).toBe("magneticmount");
  });

  it("ignores root and www domains", () => {
    expect(extractSubdomainSlug("fastaisolution.com")).toBeNull();
    expect(extractSubdomainSlug("www.fastaisolution.com")).toBeNull();
  });

  it("handles hosts with ports", () => {
    expect(extractSubdomainSlug("ergokeyboard.fastaisolution.com:3000")).toBe("ergokeyboard");
  });

  it("extracts subdomain from .localhost for local dev", () => {
    expect(extractSubdomainSlug("magneticphonemount.localhost:3000")).toBe("magneticphonemount");
    expect(extractSubdomainSlug("localhost:3000")).toBeNull();
  });

  it("does not rewrite app routes on a store subdomain", () => {
    const request = new NextRequest("http://magneticphonemount.localhost:3000/dashboard", {
      headers: { host: "magneticphonemount.localhost:3000" },
    });

    const response = middleware(request);

    expect(response.headers.get("x-middleware-rewrite")).toBeNull();
  });
});
