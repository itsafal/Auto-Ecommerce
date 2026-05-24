import { NextRequest, NextResponse } from "next/server";

const DEFAULT_BASE_DOMAINS = ["fastaisolution.com", "localhost"];

function getBaseDomains() {
  const fromEnv = process.env.NEXT_PUBLIC_BASE_DOMAIN;
  if (!fromEnv) return DEFAULT_BASE_DOMAINS;
  return Array.from(new Set([fromEnv.toLowerCase(), ...DEFAULT_BASE_DOMAINS]));
}

export function extractSubdomainSlug(host: string, baseDomain?: string) {
  const cleanHost = host.split(":")[0].toLowerCase();
  const candidates = baseDomain ? [baseDomain.toLowerCase()] : getBaseDomains();

  for (const domain of candidates) {
    const suffix = `.${domain}`;
    if (!cleanHost.endsWith(suffix)) continue;
    const slug = cleanHost.slice(0, -suffix.length);
    if (!slug || slug === "www" || slug === "fastaisolution") continue;
    return slug;
  }
  return null;
}

export function middleware(req: NextRequest) {
  const host = req.headers.get("host") || "";
  const slug = extractSubdomainSlug(host);

  if (slug) {
    return NextResponse.rewrite(new URL(`/store/${slug}`, req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next|favicon.ico).*)"]
};
