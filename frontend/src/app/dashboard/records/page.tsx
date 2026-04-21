"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { dedupeLearningRecordRows, describeLearningRecordPayload, LEARNING_ACTION_LABELS } from "@/lib/learning-record";

interface RecordRow {
  id: number;
  action: string;
  payload: Record<string, unknown>;
  created_at: string;
  course_id: number | null;
  duration_sec: number;
}

const RECORD_TABS = [
  { key: "all", label: "全部" },
  { key: "exam", label: "考试" },
  { key: "qa", label: "问答" },
  { key: "course", label: "课程学习" },
  { key: "review", label: "薄弱点复习" },
] as const;

type RecordTabKey = (typeof RECORD_TABS)[number]["key"];

function actionTab(action: string): RecordTabKey {
  if (action === "start_exam" || action === "submit_exam") return "exam";
  if (action === "ask_question") return "qa";
  if (action === "review_kp_perfect") return "review";
  if (action === "view_course" || action === "read_chunk" || action === "complete_chapter" || action === "practice") {
    return "course";
  }
  return "all";
}

export default function RecordsPage() {
  const [records, setRecords] = useState<RecordRow[]>([]);
  /** 关闭后才会拉取「仅浏览课程」等高频记录 */
  const [meaningfulOnly, setMeaningfulOnly] = useState(true);
  const [activeTab, setActiveTab] = useState<RecordTabKey>("all");

  const load = useCallback(() => {
    const q = new URLSearchParams({
      limit: "40",
      meaningful: meaningfulOnly ? "true" : "false",
    });
    api.get<RecordRow[]>(`/records/me?${q}`).then((rows) => setRecords(dedupeLearningRecordRows(rows)));
  }, [meaningfulOnly]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = records.filter((r) => activeTab === "all" || actionTab(r.action) === activeTab);

  return (
    <div className="mx-auto max-w-6xl space-y-7 p-4 md:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">学习记录</h1>
          <p className="mt-1 text-sm leading-6 text-gray-500">
            {meaningfulOnly
              ? "精简：问答、考试等；已隐藏反复打开课程产生的记录"
              : "完整：含每次打开课程页的记录"}
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="shrink-0 self-start sm:self-auto"
          onClick={() => setMeaningfulOnly((v) => !v)}
        >
          {meaningfulOnly ? "显示打开课程记录" : "只显示关键动态"}
        </Button>
      </div>

      <Card>
        <CardBody className="flex flex-wrap gap-2">
        {RECORD_TABS.map((t) => {
          const count = t.key === "all" ? records.length : records.filter((r) => actionTab(r.action) === t.key).length;
          const active = activeTab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setActiveTab(t.key)}
              className={
                active
                  ? "px-3 py-1.5 rounded-full text-sm font-medium bg-brand-600 text-white"
                  : "px-3 py-1.5 rounded-full text-sm text-gray-700 bg-gray-100 hover:bg-gray-200"
              }
            >
              {t.label}（{count}）
            </button>
          );
        })}
        </CardBody>
      </Card>

      {filtered.length === 0 ? (
        <Card>
          <CardBody className="text-gray-500 text-center py-10">
            {meaningfulOnly ? "当前分类暂无关键动态，去课程里向助手提问或参加考试吧" : "当前分类暂无记录"}
          </CardBody>
        </Card>
      ) : (
        <Card>
          <CardBody className="!p-0">
            <ul className="divide-y divide-gray-50">
              {filtered.map((r) => {
                const label = LEARNING_ACTION_LABELS[r.action] || r.action;
                const line = describeLearningRecordPayload(r.action, r.payload);
                return (
                  <li key={r.id} className="flex items-start justify-between gap-3 px-4 py-3.5 sm:px-5">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm leading-6 text-gray-900">
                        <span className="font-medium">{label}</span>
                        <span className="text-gray-300 mx-1.5">·</span>
                        <span className="text-gray-700 line-clamp-2">{line}</span>
                      </div>
                    </div>
                    <time
                      className="text-[11px] text-gray-400 whitespace-nowrap shrink-0 tabular-nums pt-0.5"
                      dateTime={r.created_at}
                    >
                      {formatDate(r.created_at)}
                    </time>
                  </li>
                );
              })}
            </ul>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
