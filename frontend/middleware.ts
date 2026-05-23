import { NextRequest, NextResponse } from "next/server";

export function extractSubdomainSlug(host: string, baseDomain = "fastaisolution.com") {
  const cleanHost = host.split(":")[0].toLowerCase();
  if (!cleanHost.endsWith(baseDomain)) {
    return null;
  }

  const suffix = `.${baseDomain}`;
  if (!cleanHost.endsWith(suffix)) {
    return null;
  }

  const slug = cleanHost.slice(0, -suffix.length);
  if (!slug || slug === "www" || slug === "fastaisolution") {
    return null;
  }
  return slug;
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
