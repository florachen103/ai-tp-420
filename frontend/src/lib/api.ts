/**
 * 后端 API 客户端。所有请求统一经这里，便于处理鉴权、错误、类型。
 */

const BASE =
  (globalThis as { process?: { env?: Record<string, string | undefined> } })
    .process?.env?.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("tp_token");
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem("tp_token", token);
  else localStorage.removeItem("tp_token");
}

async function request<T>(
  path: string,
  opts: RequestInit & { json?: unknown; form?: FormData } = {}
): Promise<T> {
  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string> | undefined),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let body: BodyInit | undefined = opts.body as BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }

  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers,
    body,
  });

  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    const detail = normalizeErrorDetail(data, res.status);
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

function safeJson(t: string) {
  try {
    return JSON.parse(t);
  } catch {
    return t;
  }
}

/** FastAPI：422 时 detail 常为对象数组；其它错误可能是字符串 */
export function normalizeErrorDetail(data: unknown, status: number): string {
  if (!data || typeof data !== "object") {
    return `请求失败 (${status})`;
  }
  const d = (data as { detail?: unknown; message?: unknown }).detail;
  const msg = (data as { message?: unknown }).message;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    const parts = d
      .map((item: unknown) => {
        if (item && typeof item === "object" && "msg" in item) {
          const loc = (item as { loc?: unknown[] }).loc;
          const field =
            Array.isArray(loc) && loc.length
              ? String(loc[loc.length - 1])
              : "";
          return field ? `${field}: ${(item as { msg: string }).msg}` : (item as { msg: string }).msg;
        }
        return String(item);
      })
      .filter(Boolean);
    if (parts.length) return parts.join("；");
  }
  if (typeof msg === "string") return msg;
  return `请求失败 (${status})`;
}

export const api = {
  get: <T>(p: string) => request<T>(p, { method: "GET" }),
  post: <T>(p: string, json?: unknown) =>
    request<T>(p, { method: "POST", json }),
  patch: <T>(p: string, json?: unknown) =>
    request<T>(p, { method: "PATCH", json }),
  del: <T>(p: string) => request<T>(p, { method: "DELETE" }),
  /**
   * multipart 上传，支持进度 0–100（基于 XMLHttpRequest.upload）。
   */
  upload: <T>(path: string, file: File, onProgress?: (percent: number) => void): Promise<T> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE}${path}`);
      const token = getToken();
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

      xhr.upload.onprogress = (e) => {
        if (!onProgress) return;
        if (e.lengthComputable && e.total > 0) {
          onProgress(Math.min(100, Math.round((e.loaded / e.total) * 100)));
        }
      };

      xhr.onload = () => {
        const text = xhr.responseText || "";
        let data: unknown = null;
        try {
          data = text ? JSON.parse(text) : null;
        } catch {
          data = text;
        }
        if (xhr.status < 200 || xhr.status >= 300) {
          reject(new ApiError(xhr.status, normalizeErrorDetail(data, xhr.status)));
          return;
        }
        resolve(data as T);
      };
      xhr.onerror = () => reject(new ApiError(0, "网络错误，上传中断"));
      xhr.ontimeout = () => reject(new ApiError(0, "上传超时"));

      const fd = new FormData();
      fd.append("file", file);
      xhr.send(fd);
    });
  },
};
