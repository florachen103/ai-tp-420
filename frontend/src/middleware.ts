import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** 仅域名，无路径，例如 https://xxx.onrender.com */
function backendOrigin(): string | null {
  const o = process.env.BACKEND_ORIGIN?.trim();
  if (!o) return null;
  return o.replace(/\/$/, "");
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (pathname === "/favicon.ico") {
    return NextResponse.rewrite(new URL("/favicon.svg", request.url));
  }

  const origin = backendOrigin();
  if (origin && pathname.startsWith("/api/v1")) {
    return NextResponse.rewrite(new URL(`${origin}${pathname}${search}`));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/favicon.ico", "/api/v1/:path*"],
};
