"use client";

import { cn } from "@/lib/utils";

export function ProgressBar({
  value,
  className,
  label,
}: {
  /** 0–100 */
  value: number;
  className?: string;
  /** 条下方说明，可选 */
  label?: string;
}) {
  const v = Math.min(100, Math.max(0, Math.round(value)));
  return (
    <div className={cn("w-full", className)}>
      <div className="flex justify-between text-xs text-gray-600 mb-1">
        <span>{label ?? "进度"}</span>
        <span className="font-medium tabular-nums text-gray-800">{v}%</span>
      </div>
      <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-gray-300 via-brand-500/85 to-brand-400/90 transition-[width] duration-300 ease-out"
          style={{ width: `${v}%` }}
        />
      </div>
    </div>
  );
}
