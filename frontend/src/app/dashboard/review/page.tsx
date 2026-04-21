"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, BookMarked, RotateCcw } from "lucide-react";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { QuestionReview } from "@/types/api";
import { QUESTION_DIFFICULTY_LABEL, QUESTION_TYPE_LABEL } from "@/lib/ui-labels";
import { cn } from "@/lib/utils";

function judgeOptions(q: QuestionReview) {
  if (q.type !== "judge") return q.options;
  if (q.options?.length) return q.options;
  return [
    { key: "A", text: "正确" },
    { key: "B", text: "错误" },
  ];
}

function normAnswerList(a: string[]): string {
  return [...a].map((s) => s.trim()).filter(Boolean).sort().join("\u0000");
}

/** 与参考答案是否一致（多选按集合比较；填空/简答去空白后忽略大小写） */
function isAnswerCorrect(q: QuestionReview, user: string[]): boolean {
  const correct = q.answer ?? [];
  if (q.type === "multiple") {
    return normAnswerList(user) === normAnswerList(correct);
  }
  if (q.type === "single" || q.type === "judge") {
    return (user[0] ?? "") === (correct[0] ?? "");
  }
  const u = (user[0] ?? "").trim().toLowerCase();
  const c = (correct[0] ?? "").trim().toLowerCase();
  if (!u && !c) return true;
  return u === c && u.length > 0;
}

function ReviewQuestionInput({
  q,
  value,
  onChange,
  disabled,
}: {
  q: QuestionReview;
  value: string[];
  onChange: (v: string[]) => void;
  disabled?: boolean;
}) {
  if (q.type === "single" || q.type === "judge") {
    const opts = judgeOptions(q);
    return (
      <div className="space-y-2">
        {(opts.length ? opts : [{ key: "A", text: "" }]).map((o) => (
          <label
            key={o.key}
            className={cn(
              "flex items-start gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition text-sm",
              disabled && "pointer-events-none opacity-80",
              value[0] === o.key ? "border-brand-500 bg-brand-50" : "border-gray-200 hover:border-gray-300 bg-white"
            )}
          >
            <input
              type="radio"
              className="mt-0.5"
              checked={value[0] === o.key}
              disabled={disabled}
              onChange={() => onChange([o.key])}
            />
            <span className="text-gray-800">
              <b className="text-gray-700">{o.key}.</b> {o.text}
            </span>
          </label>
        ))}
      </div>
    );
  }
  if (q.type === "multiple") {
    if (!q.options?.length) {
      return <p className="text-xs text-amber-700">该题暂无选项数据，请切换到「浏览复习」查看答案。</p>;
    }
    return (
      <div className="space-y-2">
        {q.options.map((o) => {
          const checked = value.includes(o.key);
          return (
            <label
              key={o.key}
              className={cn(
                "flex items-start gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition text-sm",
                disabled && "pointer-events-none opacity-80",
                checked ? "border-brand-500 bg-brand-50" : "border-gray-200 hover:border-gray-300 bg-white"
              )}
            >
              <input
                type="checkbox"
                className="mt-0.5"
                checked={checked}
                disabled={disabled}
                onChange={(e) => {
                  if (e.target.checked) onChange([...value, o.key].sort());
                  else onChange(value.filter((k) => k !== o.key));
                }}
              />
              <span className="text-gray-800">
                <b className="text-gray-700">{o.key}.</b> {o.text}
              </span>
            </label>
          );
        })}
      </div>
    );
  }
  return (
    <Textarea
      value={value[0] || ""}
      onChange={(e) => onChange([e.target.value])}
      disabled={disabled}
      placeholder={q.type === "short" ? "请输入作答要点" : "请输入答案"}
      rows={q.type === "short" ? 4 : 2}
      className="text-sm"
    />
  );
}

type ReviewView = "study" | "drill" | "drill_done";

interface KpMasteryStatus {
  knowledge_point: string;
  rounds: number;
  master_rounds: number;
  remaining: number;
  mastered: boolean;
}

function ReviewBody() {
  const search = useSearchParams();
  const kpRaw = search.get("kp")?.trim() ?? "";
  const [list, setList] = useState<QuestionReview[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<ReviewView>("study");
  const [answers, setAnswers] = useState<Record<number, string[]>>({});
  const [studyMountKey, setStudyMountKey] = useState(0);
  const [mastery, setMastery] = useState<KpMasteryStatus | null>(null);
  /** 每进入一轮自测递增，用于全对上报去重（含 Strict Mode 双调用） */
  const drillEpochRef = useRef(0);

  const resetDrill = useCallback(() => {
    drillEpochRef.current += 1;
    setAnswers({});
    setView("drill");
  }, []);

  useEffect(() => {
    if (!kpRaw) {
      setList([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const q = encodeURIComponent(kpRaw);
    api
      .get<QuestionReview[]>(`/questions/review-by-knowledge?knowledge_point=${q}`)
      .then((rows) => {
        setList(rows);
        setView("study");
        setAnswers({});
        setStudyMountKey((k) => k + 1);
      })
      .catch((err) => {
        const msg = err instanceof ApiError ? err.detail : "加载失败";
        toast.error(msg);
        setList([]);
      })
      .finally(() => setLoading(false));

    api
      .get<KpMasteryStatus>(`/records/me/review-kp-status?knowledge_point=${encodeURIComponent(kpRaw)}`)
      .then(setMastery)
      .catch(() => setMastery(null));
  }, [kpRaw]);

  const setAns = useCallback((q: QuestionReview, val: string[]) => {
    setAnswers((m) => ({ ...m, [q.id]: val }));
  }, []);

  const drillStats = useMemo(() => {
    if (!list || view !== "drill_done") return null;
    let ok = 0;
    for (const q of list) {
      if (isAnswerCorrect(q, answers[q.id] || [])) ok += 1;
    }
    return { ok, total: list.length };
  }, [list, view, answers]);

  useEffect(() => {
    if (view !== "drill_done" || !list?.length || !drillStats) return;
    if (drillStats.ok !== drillStats.total) return;
    if (typeof window === "undefined") return;
    const storageKey = `kpPerfect:${kpRaw}|${drillEpochRef.current}|${list.length}|${list.map((q) => q.id).join(",")}`;
    if (sessionStorage.getItem(storageKey)) return;
    sessionStorage.setItem(storageKey, "1");
    api
      .post("/records/me/review-kp-perfect", {
        knowledge_point: kpRaw,
        question_count: list.length,
      })
      .then(() => {
        api
          .get<KpMasteryStatus>(`/records/me/review-kp-status?knowledge_point=${encodeURIComponent(kpRaw)}`)
          .then(setMastery)
          .catch(() => undefined);
      })
      .catch(() => {
        sessionStorage.removeItem(storageKey);
      });
  }, [view, list, drillStats, kpRaw]);

  if (!kpRaw) {
    return (
      <div className="p-4 md:p-8 max-w-3xl mx-auto">
        <p className="text-sm text-gray-500">请从「学习概览」里点击某个薄弱知识点进入复习。</p>
        <Link
          href="/dashboard"
          className="mt-4 inline-flex h-10 items-center justify-center rounded-lg border border-gray-200 bg-white px-4 text-sm text-gray-700 hover:border-gray-300 hover:bg-gray-50"
        >
          返回学习概览
        </Link>
      </div>
    );
  }

  if (loading) return <div className="p-6 text-gray-500">加载题目中…</div>;

  const empty = !list || list.length === 0;

  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto pb-24">
      <div className="mb-6">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 mb-3"
        >
          <ArrowLeft className="h-4 w-4" />
          学习概览
        </Link>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <BookMarked className="h-6 w-6 text-brand-600 shrink-0" />
              薄弱知识点复习
            </h1>
            <p className="text-sm text-gray-600 mt-1">
              知识点：<span className="font-medium text-brand-800">{kpRaw}</span>
            </p>
            <p className="text-xs text-gray-500 mt-1.5 max-w-xl leading-relaxed">
              在「自测」里点击「核对答案」且<strong>本轮全部答对</strong>会累计掌握次数；近 90 天内同一知识点累计
              <strong>满 3 次全对</strong>后，将从学习概览的薄弱列表中移除（考试错题仍会保留历史记录）。
            </p>
            {mastery && (
              <p className={cn(
                "mt-2 text-sm rounded-lg px-3 py-2 inline-block border",
                mastery.mastered
                  ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                  : "text-amber-800 bg-amber-50 border-amber-200"
              )}>
                已累计全对 <strong>{mastery.rounds}</strong>/<strong>{mastery.master_rounds}</strong> 次
                {mastery.mastered ? "，该知识点已达标，将不再出现在薄弱列表。" : `，还需 ${mastery.remaining} 次。`}
              </p>
            )}
          </div>
          {!empty && view === "study" && (
            <div className="flex flex-wrap gap-2 shrink-0">
              <Button type="button" variant="secondary" size="sm" onClick={() => setStudyMountKey((k) => k + 1)}>
                <RotateCcw className="h-3.5 w-3.5" />
                收起解析再来
              </Button>
              <Button type="button" size="sm" onClick={resetDrill}>
                自测再做一遍
              </Button>
            </div>
          )}
          {!empty && view === "drill" && (
            <div className="flex flex-wrap gap-2 shrink-0">
              <Button type="button" variant="secondary" size="sm" onClick={() => setView("study")}>
                返回浏览复习
              </Button>
              <Button type="button" size="sm" onClick={() => setView("drill_done")}>
                核对答案
              </Button>
            </div>
          )}
          {!empty && view === "drill_done" && drillStats && (
            <div className="flex flex-col items-stretch gap-2 sm:items-end shrink-0">
              <p className="text-sm text-gray-600 text-right">
                本轮答对{" "}
                <span className="font-semibold text-brand-700 tabular-nums">
                  {drillStats.ok}/{drillStats.total}
                </span>
              </p>
              {drillStats.ok === drillStats.total && drillStats.total > 0 && (
                <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-2.5 py-1.5 text-right max-w-md sm:ml-auto">
                  本轮全对已记录。累计 3 次全对后，该知识点不再出现在薄弱列表。
                </p>
              )}
              <div className="flex flex-wrap gap-2 justify-end">
                <Button type="button" variant="secondary" size="sm" onClick={() => setView("study")}>
                  返回浏览复习
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => {
                    drillEpochRef.current += 1;
                    setAnswers({});
                    setView("drill");
                  }}
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  再做一轮
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {empty ? (
        <Card>
          <CardBody className="text-sm text-gray-600 leading-relaxed">
            <p>暂无包含该知识点的题目，或你尚未参加过相关考试。</p>
            <p className="mt-2 text-gray-500">
              请先完成至少一次考试，系统会把你考过的课程里的题目按知识点汇总到这里。
            </p>
            <Link
              href="/dashboard/exams"
              className="mt-4 inline-flex h-10 items-center justify-center rounded-lg bg-brand-500 px-4 text-sm font-medium text-white shadow-sm hover:bg-brand-600"
            >
              去考试
            </Link>
          </CardBody>
        </Card>
      ) : view === "study" ? (
        <ul key={studyMountKey} className="space-y-4">
          {list!.map((q, i) => (
            <li key={q.id}>
              <Card className="border border-gray-200 shadow-sm">
                <CardBody>
                  <div className="text-xs text-gray-400 mb-2">
                    第 {i + 1} 题 · {QUESTION_TYPE_LABEL[q.type] ?? "题目"} ·{" "}
                    {QUESTION_DIFFICULTY_LABEL[q.difficulty] ?? "难度"}
                  </div>
                  <h2 className="text-base font-medium text-gray-900 leading-relaxed">{q.stem}</h2>

                  {(q.type === "single" || q.type === "multiple" || q.type === "judge") && (
                    <ul className="mt-4 space-y-2">
                      {judgeOptions(q).map((o) => (
                        <li
                          key={o.key}
                          className="rounded-lg border border-gray-100 bg-gray-50/80 px-3 py-2 text-sm text-gray-800"
                        >
                          <span className="font-semibold text-gray-700">{o.key}.</span> {o.text}
                        </li>
                      ))}
                    </ul>
                  )}

                  <details className="mt-4 rounded-lg border border-brand-100 bg-brand-50/40 px-3 py-2 text-sm">
                    <summary className="cursor-pointer select-none font-medium text-brand-800">
                      查看答案与解析
                    </summary>
                    <div className="mt-3 space-y-2 text-gray-800 border-t border-brand-100/80 pt-3">
                      <p>
                        <span className="text-gray-500">参考答案：</span>
                        <span className="font-semibold text-emerald-800">{q.answer?.join("、") || "—"}</span>
                      </p>
                      {q.explanation ? (
                        <p className="text-gray-600 leading-relaxed">
                          <span className="text-gray-500">解析：</span>
                          {q.explanation}
                        </p>
                      ) : (
                        <p className="text-gray-400 text-xs">暂无文字解析</p>
                      )}
                    </div>
                  </details>
                </CardBody>
              </Card>
            </li>
          ))}
        </ul>
      ) : (
        <div className="space-y-4">
          {view === "drill" && (
            <p className="text-sm text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
              先凭记忆作答，完成后点右上角「核对答案」查看对错与解析。
            </p>
          )}
          <ul className="space-y-4">
            {list!.map((q, i) => {
              const userAns = answers[q.id] || [];
              const correct = view === "drill_done" ? isAnswerCorrect(q, userAns) : null;
              const showInputs =
                q.type === "single" || q.type === "multiple" || q.type === "judge" || q.type === "fill" || q.type === "short";

              return (
                <li key={q.id}>
                  <Card
                    className={cn(
                      "border shadow-sm",
                      view === "drill_done"
                        ? correct
                          ? "border-emerald-200 bg-emerald-50/20"
                          : correct === false
                            ? "border-rose-200 bg-rose-50/20"
                            : "border-gray-200"
                        : "border-gray-200"
                    )}
                  >
                    <CardBody>
                      <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                        <div className="text-xs text-gray-400">
                          第 {i + 1} 题 · {QUESTION_TYPE_LABEL[q.type] ?? "题目"} ·{" "}
                          {QUESTION_DIFFICULTY_LABEL[q.difficulty] ?? "难度"}
                        </div>
                        {view === "drill_done" && (
                          <span
                            className={cn(
                              "text-xs font-medium px-2 py-0.5 rounded-full shrink-0",
                              correct ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"
                            )}
                          >
                            {correct ? "正确" : "有误"}
                          </span>
                        )}
                      </div>
                      <h2 className="text-base font-medium text-gray-900 leading-relaxed">{q.stem}</h2>

                      {showInputs && (
                        <div className="mt-4">
                          <ReviewQuestionInput
                            q={q}
                            value={userAns}
                            onChange={(v) => setAns(q, v)}
                            disabled={view === "drill_done"}
                          />
                        </div>
                      )}

                      {view === "drill_done" && (
                        <div className="mt-4 rounded-lg border border-gray-100 bg-gray-50/80 px-3 py-2.5 text-sm space-y-2">
                          <p className="text-gray-700">
                            <span className="text-gray-500">你的作答：</span>
                            <span className="font-medium">{userAns.length ? userAns.join("、") : "未作答"}</span>
                          </p>
                          <p className="text-gray-700">
                            <span className="text-gray-500">参考答案：</span>
                            <span className="font-semibold text-emerald-800">{q.answer?.join("、") || "—"}</span>
                          </p>
                          {q.explanation ? (
                            <p className="text-gray-600 leading-relaxed pt-1 border-t border-gray-200/80">
                              <span className="text-gray-500">解析：</span>
                              {q.explanation}
                            </p>
                          ) : null}
                        </div>
                      )}
                    </CardBody>
                  </Card>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function WeakKnowledgeReviewPage() {
  return (
    <Suspense fallback={<div className="p-6 text-gray-500">加载中…</div>}>
      <ReviewBody />
    </Suspense>
  );
}
