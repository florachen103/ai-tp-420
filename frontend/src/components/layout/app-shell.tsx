"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  ClipboardList,
  FileCheck2,
  FilePenLine,
  Files,
  FolderKanban,
  History,
  LayoutDashboard,
  LibraryBig,
  LogOut,
  Network,
  Settings,
  Type,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-store";
import { cn } from "@/lib/utils";

const BRAND_LOGO_URL = "https://i.hd-r.cn/d5c9922f-0981-4aa5-b03a-0132e161c657.png";

const NAV = [
  { href: "/dashboard/knowledge", label: "知识库", icon: LibraryBig },
  { href: "/dashboard/courses", label: "培训项目", icon: BookOpen },
  { href: "/dashboard/exams", label: "考试", icon: ClipboardList },
  { href: "/dashboard/records", label: "记录", icon: History },
];

const KNOWLEDGE_ADMIN_NAV = [
  { href: "/admin/knowledge/spaces", label: "知识空间", icon: FolderKanban, roles: ["admin", "manager", "editor", "reviewer", "publisher"] },
  { href: "/admin/knowledge/wiki", label: "Wiki目录", icon: Network, roles: ["admin", "manager", "editor", "reviewer", "publisher"] },
  { href: "/admin/knowledge/drafts", label: "知识草稿", icon: FilePenLine, roles: ["admin", "manager", "editor", "reviewer", "publisher"] },
  { href: "/admin/knowledge/review", label: "审核工作台", icon: FileCheck2, roles: ["admin", "manager", "reviewer"] },
  { href: "/admin/knowledge/published", label: "已发布知识", icon: Files, roles: ["admin", "manager", "editor", "reviewer", "publisher"] },
  { href: "/admin/rag-metrics", label: "知识监控", icon: BarChart3, roles: ["admin", "manager", "reviewer", "publisher"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, init, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [uiMode, setUiMode] = useState<"normal" | "senior">("senior");

  useEffect(() => {
    init();
  }, [init]);

  useEffect(() => {
    if (user === null && typeof window !== "undefined") {
      const token = localStorage.getItem("tp_token");
      if (!token) router.push("/login");
    }
  }, [user, router]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = localStorage.getItem("tp_ui_mode");
    const mode = saved === "normal" || saved === "senior" ? saved : "senior";
    setUiMode(mode);
    document.documentElement.setAttribute("data-ui-mode", mode);
  }, []);

  function toggleUiMode() {
    const next: "normal" | "senior" = uiMode === "senior" ? "normal" : "senior";
    setUiMode(next);
    if (typeof window !== "undefined") {
      localStorage.setItem("tp_ui_mode", next);
      document.documentElement.setAttribute("data-ui-mode", next);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-gray-50 md:h-screen md:min-h-0 md:flex-row md:overflow-hidden">
      {/* PC 侧边栏：不参与主区滚动，始终贴左固定高度 */}
      <aside className="hidden md:flex md:h-full md:w-72 md:shrink-0 md:flex-col md:overflow-hidden bg-white border-r border-gray-100">
        <div className="flex h-20 shrink-0 items-center gap-3 border-b border-gray-100 px-6">
          <Image
            src={BRAND_LOGO_URL}
            alt="智能培训平台"
            width={40}
            height={40}
            className="h-10 w-10 shrink-0 rounded-lg object-contain"
            priority
          />
          <span className="text-xl font-bold text-gray-900">知识资产中台</span>
        </div>
        <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto p-3">
          <div className="px-4 pb-2 pt-1 text-[11px] font-medium tracking-wide text-gray-400">知识消费</div>
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-4 h-12 rounded-lg text-base transition",
                  active
                    ? "bg-brand-50 text-brand-700 font-medium"
                    : "text-gray-600 hover:bg-gray-50"
                )}
              >
                <Icon className="h-5 w-5" />
                {item.label}
              </Link>
            );
          })}
          {user && user.role !== "learner" && (
            <>
              <div className="px-4 pb-2 pt-4 text-[11px] font-medium tracking-wide text-gray-400">知识生产</div>
              {KNOWLEDGE_ADMIN_NAV.filter((item) => user?.role && item.roles.includes(user.role)).map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 px-4 h-12 rounded-lg text-base",
                      active
                        ? "bg-brand-50 text-brand-700 font-medium"
                        : "text-gray-600 hover:bg-gray-50"
                    )}
                  >
                    <Icon className="h-5 w-5" />
                    {item.label}
                  </Link>
                );
              })}
              <div className="px-4 pb-2 pt-4 text-[11px] font-medium tracking-wide text-gray-400">培训运营</div>
              <Link
                href="/admin/courses"
                className={cn(
                  "flex items-center gap-3 px-4 h-12 rounded-lg text-base",
                  pathname === "/admin/courses" || pathname.startsWith("/admin/courses/")
                    ? "bg-brand-50 text-brand-700 font-medium"
                    : "text-gray-600 hover:bg-gray-50"
                )}
              >
                <Settings className="h-5 w-5" />
                培训项目
              </Link>
            </>
          )}
        </nav>
        <div className="shrink-0 border-t border-gray-100 p-3">
          <button
            onClick={toggleUiMode}
            className="mb-2 flex w-full items-center justify-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100"
            aria-label="切换阅读模式"
          >
            <Type className="h-4 w-4" />
            {uiMode === "senior" ? "切换为普通模式" : "切换为适老模式"}
          </button>
          <div className="flex items-center gap-3 px-3 py-2.5">
            <div className="h-10 w-10 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold text-base">
              {user?.name?.[0]?.toUpperCase() || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-base font-semibold text-gray-900 truncate">{user?.name}</div>
              <div className="text-sm text-gray-500 truncate">{user?.department || user?.email}</div>
            </div>
            <button
              onClick={() => {
                logout();
                router.push("/login");
              }}
              className="text-gray-400 hover:text-gray-600"
              aria-label="退出"
            >
              <LogOut className="h-5 w-5" />
            </button>
          </div>
        </div>
      </aside>

      {/* 主列：桌面端仅此处纵向滚动 */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col md:overflow-hidden">
        {/* 移动端顶部条 */}
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-gray-100 bg-white px-4 md:hidden">
        <div className="flex items-center gap-2">
          <Image
            src={BRAND_LOGO_URL}
            alt="智能培训平台"
            width={32}
            height={32}
            className="h-8 w-8 shrink-0 rounded-md object-contain"
            priority
          />
          <span className="text-lg font-semibold text-gray-900">知识中台</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={toggleUiMode}
            className="text-gray-600 text-sm"
            aria-label="切换阅读模式"
          >
            {uiMode === "senior" ? "普通" : "适老"}
          </button>
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="text-gray-600 text-base"
          >
            退出
          </button>
        </div>
        </header>

        <main className="min-w-0 flex-1 pb-20 md:min-h-0 md:overflow-y-auto md:pb-6">{children}</main>

        {/* 移动端底部导航 */}
        <nav className="fixed inset-x-0 bottom-0 z-20 grid h-20 grid-cols-4 border-t border-gray-100 bg-white md:hidden">
        {NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center justify-center gap-1 text-sm",
                active ? "text-brand-600" : "text-gray-500"
              )}
            >
              <Icon className="h-6 w-6" />
              {item.label}
            </Link>
          );
        })}
        </nav>
      </div>
    </div>
  );
}
