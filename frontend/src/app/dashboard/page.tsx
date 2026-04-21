"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardBody } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { DashboardStats } from "@/types/api";
import { formatDate } from "@/lib/utils";
import { describeLearningRecordPayload, LEARNING_ACTION_LABELS } from "@/lib/learning-record";
import { BookOpen, Clock, GraduationCap, Target, TrendingUp } from "lucide-react";

export default function DashboardHome() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<DashboardStats>("/records/dashboard/me")
      .then(setStats)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-gray-500">加载中...</div>;
  if (!stats) return <div className="p-6 text-gray-500">数据加载失败</div>;

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">学习概览</h1>
      <p className="text-sm text-gray-500 mb-6">近 90 天的学习数据</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-6">
        <StatCard
          icon={<Clock className="h-5 w-5" />}
          label="学习时长"
          value={`${stats.total_learning_minutes} 分钟`}
          color="bg-blue-50 text-blue-600"
        />
        <StatCard
          icon={<BookOpen className="h-5 w-5" />}
          label="学过课程"
          value={`${stats.courses_viewed}`}
          color="bg-emerald-50 text-emerald-600"
        />
        <StatCard
          icon={<GraduationCap className="h-5 w-5" />}
          label="参加考试"
          value={`${stats.exams_taken}`}
          sub={`通过 ${stats.exams_passed}`}
          color="bg-amber-50 text-amber-600"
        />
        <StatCard
          icon={<TrendingUp className="h-5 w-5" />}
          label="平均分"
          value={stats.average_score != null ? stats.average_score.toFixed(1) : "—"}
          color="bg-rose-50 text-rose-600"
        />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardBody>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Target className="h-4 w-4 text-brand-600" /> 薄弱知识点
            </h3>
            {stats.weak_knowledge_points.length === 0 ? (
              <p className="text-sm text-gray-500">暂无数据，先去参加几次考试吧</p>
            ) : (
              <ul className="space-y-3">
                {stats.weak_knowledge_points.slice(0, 8).map((kp) => (
                  <li key={kp.point}>
                    <Link
                      href={`/dashboard/review?kp=${encodeURIComponent(kp.point)}`}
                      className="group block rounded-lg -mx-1 px-1 py-1.5 transition hover:bg-brand-50/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand-400"
                    >
                      <div className="flex justify-between text-sm mb-1 gap-2">
                        <span className="text-gray-800 font-medium text-brand-700 underline-offset-2 group-hover:underline">
                          {kp.point}
                        </span>
                        <span className="text-rose-500 font-medium shrink-0 tabular-nums">
                          错率 {(kp.wrong_rate * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-rose-400 to-rose-600"
                          style={{ width: `${kp.wrong_rate * 100}%` }}
                        />
                      </div>
                      <p className="text-[11px] text-gray-400 mt-1">点击进入复习</p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <div className="mb-3">
              <h3 className="font-semibold text-gray-900">最近活动</h3>
              <p className="text-xs text-gray-400 mt-0.5">不含「仅打开课程」自动记录</p>
            </div>
            {stats.recent_records.length === 0 ? (
              <p className="text-sm text-gray-500">还没有学习记录</p>
            ) : (
              <ul className="space-y-3">
                {stats.recent_records.map((r) => (
                  <li key={r.id} className="border-b border-gray-50 last:border-0 pb-3 last:pb-0">
                    <div className="flex justify-between gap-3 items-start">
                      <span className="text-sm font-medium text-gray-800">
                        {LEARNING_ACTION_LABELS[r.action] ?? "其它学习活动"}
                      </span>
                      <span className="text-gray-400 text-xs shrink-0 tabular-nums">{formatDate(r.created_at)}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1 leading-relaxed line-clamp-2">
                      {describeLearningRecordPayload(r.action, r.payload)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function StatCard({
  icon, label, value, sub, color,
}: {
  icon: React.ReactNode; label: string; value: string; sub?: string; color: string;
}) {
  return (
    <Card>
      <CardBody className="!p-4">
        <div className={`inline-flex h-9 w-9 rounded-lg items-center justify-center ${color}`}>{icon}</div>
        <div className="mt-3 text-2xl font-semibold text-gray-900">{value}</div>
        <div className="text-xs text-gray-500 mt-1">{label}{sub && <span className="ml-1 text-emerald-600">· {sub}</span>}</div>
      </CardBody>
    </Card>
  );
}
