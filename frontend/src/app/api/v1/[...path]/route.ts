import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/** 运行时读环境变量，避免依赖 external rewrite 转发 POST（Vercel 上易 500） */
export const dynamic = "force-dynamic";

const HOP_BY_HOP = new Set([
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
]);

function backendBase(): string {
  return (process.env.BACKEND_ORIGIN || "").trim().replace(/\/$/, "");
}

function forwardHeaders(req: NextRequest): Headers {
  const out = new Headers();
  req.headers.forEach((value, key) => {
    if (HOP_BY_HOP.has(key.toLowerCase())) return;
    out.set(key, value);
  });
  return out;
}

async function proxy(req: NextRequest, segments: string[]) {
  const base = backendBase();
  if (!base) {
    return NextResponse.json({ detail: "BACKEND_ORIGIN 未配置" }, { status: 503 });
  }
  const rest = segments.length ? segments.join("/") : "";
  const upstreamPath = rest ? `/api/v1/${rest}` : "/api/v1";
  const url = `${base}${upstreamPath}${req.nextUrl.search}`;

  const method = req.method;
  const hasBody = method !== "GET" && method !== "HEAD";
  const upstream = await fetch(url, {
    method,
    headers: forwardHeaders(req),
    body: hasBody ? await req.arrayBuffer() : undefined,
    redirect: "manual",
  });

  const outHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (k === "content-encoding" || k === "transfer-encoding") return;
    outHeaders.set(key, value);
  });

  return new NextResponse(upstream.body, { status: upstream.status, headers: outHeaders });
}

type Ctx = { params: { path: string[] } };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path ?? []);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path ?? []);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path ?? []);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path ?? []);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path ?? []);
}
export async function OPTIONS(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path ?? []);
}
