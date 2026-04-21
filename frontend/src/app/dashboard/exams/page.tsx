"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Attempt, Exam } from "@/types/api";
import { formatDate } from "@/lib/utils";
import { ClipboardList } from "lucide-react";

function scorePercent(score: number | null, maxScore: number): string | null {
  if (score == null || maxScore <= 0) return null;
  return `${Math.round((score / maxScore) * 1000) / 10}%`;
}

const attemptStatusLabel: Record<string, string> = {
  in_progress: "作答中",
  submitted: "待批改",
  graded: "已出分",
  expired: "已过期",
};

export default function ExamsPage() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [attempts, setAttempts] = useState<Attempt[]>([]);

  useEffect(() => {
    api.get<Exam[]>("/exams").then(setExams);
    api.get<Attempt[]>("/exams/attempts/me").then(setAttempts);
  }, []);

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">在线考试</h1>
        <p className="text-sm text-gray-500">选择考试进行作答</p>
      </div>

      <div>
        <h2 className="font-semibold text-gray-800 mb-3">可参加的考试</h2>
        {exams.length === 0 ? (
          <Card>
            <CardBody className="text-center py-10 text-gray-500">
              <ClipboardList className="h-10 w-10 mx-auto mb-2 text-gray-300" />
              暂无考试
            </CardBody>
          </Card>
        ) : (
          <div className="grid md:grid-cols-2 gap-4">
            {exams.map((e) => (
              <Card key={e.id}>
                <CardBody>
                  <h3 className="font-semibold text-gray-900">{e.title}</h3>
                  {e.description && <p className="mt-1 text-sm text-gray-500">{e.description}</p>}
                  <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
                    <span>时长 {e.duration_minutes} 分钟</span>
                    <span>合格分 {e.pass_score}</span>
                  </div>
                  <div className="mt-4">
                    <Link href={`/dashboard/exams/${e.id}/take`}>
                      <Button size="sm">开始考试</Button>
                    </Link>
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>
        )}
      </div>

      <div>
        <h2 className="font-semibold text-gray-800 mb-3">我的历史成绩</h2>
        {attempts.length === 0 ? (
          <div className="text-sm text-gray-500">还没有考试记录</div>
        ) : (
          <Card>
            <CardBody className="!p-0 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-500 text-xs">
                  <tr>
                    <th className="text-left px-4 py-2 font-normal">考试</th>
                    <th className="text-left px-4 py-2 font-normal">得分（百分比）</th>
                    <th className="text-left px-4 py-2 font-normal">状态</th>
                    <th className="text-left px-4 py-2 font-normal">时间</th>
                  </tr>
                </thead>
                <tbody>
                  {attempts.map((a) => {
                    const examTitle = exams.find((e) => e.id === a.exam_id)?.title;
                    const pct = scorePercent(a.score, a.max_score);
                    const qn = typeof a.question_count === "number" ? a.question_count : 0;
                    return (
                    <tr key={a.id} className="border-t border-gray-50">
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900">{examTitle ?? `考试编号 ${a.exam_id}`}</div>
                        <div className="text-xs text-gray-400">作答编号 {a.id}</div>
                      </td>
                      <td className="px-4 py-3">
                        {pct != null ? (
                          <div>
                            <span className="text-lg font-semibold text-gray-900 tabular-nums">{pct}</span>
                            <div className="text-xs text-gray-500 mt-0.5">
                              卷面分 <span className="tabular-nums">{a.score}</span>
                              <span className="text-gray-400"> / {a.max_score}</span>
                            </div>
                          </div>
                        ) : (
                          <div>
                            <span className="text-gray-400 tabular-nums">—</span>
                            <div className="text-xs text-gray-500 mt-0.5">
                              满分 <span className="tabular-nums">{a.max_score}</span>
                              {qn > 0 && (
                                <span className="text-gray-400">
                                  {" · 共 "}{qn} 题
                                  {a.status === "in_progress"
                                    ? "（未交卷无得分）"
                                    : a.status === "submitted"
                                      ? "（待批改）"
                                      : ""}
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <span className={
                          a.status === "graded" ? "text-emerald-600 font-medium" :
                          a.status === "in_progress" ? "text-amber-600 font-medium" : "text-gray-500"
                        }>{attemptStatusLabel[a.status] ?? "其它状态"}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-500">{formatDate(a.started_at)}</td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}
