import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/** 运行时读环境变量，转发到 Render 等后端 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function backendBase(): string {
  return (process.env.BACKEND_ORIGIN || "").trim().replace(/\/$/, "");
}

/** 只转发常见 API 头，避免把浏览器/Vercel 的一堆 hop 头带给上游导致异常 */
function forwardHeaders(req: NextRequest): Headers {
  const out = new Headers();
  const names = [
    "authorization",
    "content-type",
    "accept",
    "accept-language",
    "if-match",
    "if-none-match",
  ] as const;
  for (const name of names) {
    const v = req.headers.get(name);
    if (v) out.set(name, v);
  }
  return out;
}

function normalizeSegments(path: string[] | string | undefined): string[] {
  if (!path) return [];
  return Array.isArray(path) ? path : [path];
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

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method,
      headers: forwardHeaders(req),
      body: hasBody ? await req.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      {
        detail: "无法连接后端，请检查 BACKEND_ORIGIN 与 Render 服务是否可用",
        error: msg,
      },
      { status: 502 }
    );
  }

  const outHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (k === "content-encoding" || k === "transfer-encoding" || k === "content-length") return;
    outHeaders.set(key, value);
  });

  /** 缓冲响应，避免在 Vercel 上 pipe ReadableStream 偶发失败导致 500 */
  const buf = await upstream.arrayBuffer();
  return new NextResponse(buf, { status: upstream.status, headers: outHeaders });
}

type Ctx = { params: { path?: string[] | string } };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, normalizeSegments(ctx.params?.path));
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, normalizeSegments(ctx.params?.path));
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return proxy(req, normalizeSegments(ctx.params?.path));
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, normalizeSegments(ctx.params?.path));
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, normalizeSegments(ctx.params?.path));
}
export async function OPTIONS(req: NextRequest, ctx: Ctx) {
  return proxy(req, normalizeSegments(ctx.params?.path));
}
