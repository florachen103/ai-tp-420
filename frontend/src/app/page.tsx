"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("tp_token") : null;
    router.replace(token ? "/dashboard" : "/login");
  }, [router]);
  return (
    <div className="min-h-screen flex items-center justify-center text-gray-500">
      加载中...
    </div>
  );
}
