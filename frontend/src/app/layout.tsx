import type { Metadata, Viewport } from "next";
import { Toaster } from "sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "智能培训平台",
  description: "基于知识库检索的企业在线培训系统",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#E60036",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        {children}
        <Toaster position="top-center" richColors />
      </body>
    </html>
  );
}
