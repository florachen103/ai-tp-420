"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { AttemptStart, AttemptResult, Question } from "@/types/api";
import { cn } from "@/lib/utils";
import { QUESTION_DIFFICULTY_LABEL, QUESTION_TYPE_LABEL } from "@/lib/ui-labels";
import { Check, Clock, ChevronLeft, ChevronRight, X } from "lucide-react";

export default function TakeExamPage({ params }: { params: { id: string } }) {
  const examId = Number(params.id);
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<AttemptStart | null>(null);
  const [answers, setAnswers] = useState<Record<number, string[]>>({});
  const [cursor, setCursor] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number>(Date.now());
  const proctorEvents = useRef<Array<{ t: number; type: string }>>([]);

  useEffect(() => {
    api.post<AttemptStart>(`/exams/${examId}/start`)
      .then((res) => {
        setData(res);
        startRef.current = Date.now();
      })
      .catch((err) => {
        const msg = err instanceof ApiError ? err.detail : "开始考试失败";
        toast.error(msg);
        router.push("/dashboard/exams");
      })
      .finally(() => setLoading(false));
  }, [examId, router]);

  // 计时 + 切屏监测
  useEffect(() => {
    if (!data || result) return;
    const tick = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 1000);
    const onBlur = () => proctorEvents.current.push({ t: Date.now(), type: "blur" });
    const onVisibility = () => {
      if (document.hidden) proctorEvents.current.push({ t: Date.now(), type: "hidden" });
    };
    window.addEventListener("blur", onBlur);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearInterval(tick);
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [data, result]);

  const current: Question | undefined = data?.questions[cursor];
  const total = data?.questions.length ?? 0;
  const answered = useMemo(() => Object.values(answers).filter((a) => a.length > 0).length, [answers]);
  const answeredPct = total > 0 ? Math.round((answered / total) * 100) : 0;

  function setAns(q: Question, val: string[]) {
    setAnswers((m) => ({ ...m, [q.id]: val }));
  }

  async function submit() {
    if (!data) return;
    if (answered < total) {
      if (!confirm(`还有 ${total - answered} 题未作答，确认提交吗？`)) return;
    }
    setSubmitting(true);
    try {
      const payload = {
        answers: data.questions.map((q) => ({
          question_id: q.id,
          answer: answers[q.id] || [],
          time_spent_sec: 0, // 简化：未按题计时
        })),
        proctor_events: proctorEvents.current,
      };
      const res = await api.post<AttemptResult>(`/exams/attempts/${data.attempt.id}/submit`, payload);
      setResult(res);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "提交失败";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="p-6 text-gray-500">加载中...</div>;
  if (!data) return null;

  if (result) return <ResultView result={result} onClose={() => router.push("/dashboard/exams")} />;

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="p-5 md:p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div className="text-base text-gray-600">
          第 <span className="font-semibold text-gray-900">{cursor + 1}</span> / {total} 题
          <span className="ml-3 text-sm text-gray-600">
            已作答 {answered}/{total}（{answeredPct}%）
          </span>
        </div>
        <div className="flex items-center gap-2 text-base text-gray-700 font-medium">
          <Clock className="h-5 w-5" /> {mm}:{ss}
        </div>
      </div>

      <div className="flex items-center justify-between text-sm text-gray-600 mb-1">
        <span>答题完成度</span>
        <span className="font-medium tabular-nums text-gray-800">{answeredPct}%</span>
      </div>
      <div className="h-1.5 bg-gray-100 rounded mb-4 overflow-hidden">
        <div className="h-full bg-brand-500 transition-[width] duration-300" style={{ width: `${answeredPct}%` }} />
      </div>

      {current && (
        <Card>
          <CardBody>
            <div className="text-sm text-gray-500 mb-2">
              {QUESTION_TYPE_LABEL[current.type] ?? "题目"}
              · {QUESTION_DIFFICULTY_LABEL[current.difficulty] ?? "难度"}
            </div>
            <h2 className="text-2xl font-semibold text-gray-900 leading-relaxed">{current.stem}</h2>

            <div className="mt-5">
              <QuestionInput q={current} value={answers[current.id] || []} onChange={(v) => setAns(current, v)} />
            </div>

            <div className="mt-8 flex justify-between">
              <Button variant="secondary" onClick={() => setCursor(Math.max(0, cursor - 1))} disabled={cursor === 0}>
                <ChevronLeft className="h-4 w-4" /> 上一题
              </Button>
              {cursor < total - 1 ? (
                <Button onClick={() => setCursor(cursor + 1)}>
                  下一题 <ChevronRight className="h-4 w-4" />
                </Button>
              ) : (
                <Button onClick={submit} disabled={submitting}>
                  {submitting ? "交卷中..." : "提交试卷"}
                </Button>
              )}
            </div>
          </CardBody>
        </Card>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {data.questions.map((q, i) => (
          <button
            key={q.id}
            onClick={() => setCursor(i)}
            className={cn(
              "h-10 w-10 rounded text-sm border font-medium",
              i === cursor
                ? "bg-brand-500 text-white border-brand-500"
                : (answers[q.id]?.length ?? 0) > 0
                  ? "bg-brand-50 text-brand-700 border-brand-200"
                  : "bg-white text-gray-600 border-gray-200"
            )}
          >{i + 1}</button>
        ))}
      </div>
    </div>
  );
}

function QuestionInput({
  q, value, onChange,
}: {
  q: Question; value: string[]; onChange: (v: string[]) => void;
}) {
  if (q.type === "single" || q.type === "judge") {
    return (
      <div className="space-y-2">
        {(q.options.length ? q.options : [
          { key: "A", text: "正确" }, { key: "B", text: "错误" },
        ]).map((o) => (
          <label
            key={o.key}
            className={cn(
              "flex items-start gap-3 px-4 py-3 rounded-lg border cursor-pointer transition",
              value[0] === o.key ? "border-brand-500 bg-brand-50" : "border-gray-200 hover:border-gray-300"
            )}
          >
            <input
              type="radio"
              className="mt-0.5"
              checked={value[0] === o.key}
              onChange={() => onChange([o.key])}
            />
            <span className="text-lg text-gray-900 leading-relaxed"><b>{o.key}.</b> {o.text}</span>
          </label>
        ))}
      </div>
    );
  }
  if (q.type === "multiple") {
    return (
      <div className="space-y-2">
        {q.options.map((o) => {
          const checked = value.includes(o.key);
          return (
            <label
              key={o.key}
              className={cn(
                "flex items-start gap-3 px-4 py-3 rounded-lg border cursor-pointer transition",
                checked ? "border-brand-500 bg-brand-50" : "border-gray-200 hover:border-gray-300"
              )}
            >
              <input
                type="checkbox"
                className="mt-0.5"
                checked={checked}
                onChange={(e) => {
                  if (e.target.checked) onChange([...value, o.key].sort());
                  else onChange(value.filter((k) => k !== o.key));
                }}
              />
              <span className="text-lg text-gray-900 leading-relaxed"><b>{o.key}.</b> {o.text}</span>
            </label>
          );
        })}
      </div>
    );
  }
  // fill / short
  return (
    <Textarea
      value={value[0] || ""}
      onChange={(e) => onChange([e.target.value])}
      placeholder={q.type === "short" ? "请作答（系统将对照参考答案自动判分）" : "请输入答案"}
      rows={q.type === "short" ? 6 : 3}
      className="text-base leading-relaxed"
    />
  );
}

function ResultView({ result, onClose }: { result: AttemptResult; onClose: () => void }) {
  return (
    <div className="p-5 md:p-8 max-w-5xl mx-auto">
      <Card>
        <CardBody className="text-center py-10">
          <div className={`text-6xl font-bold ${result.passed ? "text-emerald-600" : "text-rose-500"}`}>
            {result.attempt.score?.toFixed(1) ?? "—"}
          </div>
          <div className="mt-2 text-lg text-gray-600">满分 {result.attempt.max_score}</div>
          <div className="mt-3 inline-flex items-center justify-center gap-1.5 px-4 py-1.5 rounded-full text-base font-semibold bg-gray-100 text-gray-800">
            {result.passed ? (
              <>
                <Check className="h-4 w-4 text-emerald-600 shrink-0" aria-hidden />
                <span>通过</span>
              </>
            ) : (
              <>
                <X className="h-4 w-4 text-rose-500 shrink-0" aria-hidden />
                <span>未通过</span>
              </>
            )}
          </div>
        </CardBody>
      </Card>

      <h3 className="mt-6 mb-3 text-2xl font-bold text-gray-900">答案详情</h3>
      <div className="space-y-3">
        {result.details.map((d, i) => (
          <Card key={d.question_id}>
            <CardBody>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="text-sm text-gray-500 mb-1">第 {i + 1} 题 · {QUESTION_TYPE_LABEL[d.type] ?? "题目"}</div>
                  <div className="text-lg text-gray-900 leading-relaxed">{d.stem}</div>
                </div>
                <span className="text-sm px-2.5 py-1 rounded whitespace-nowrap font-semibold bg-yellow-300 text-yellow-950 shadow-sm">
                  {d.score.toFixed(1)} 分
                </span>
              </div>
              <div className="mt-3 text-base space-y-2 text-gray-700 leading-relaxed">
                <div>你的答案：<span className="text-gray-900 font-medium">{d.user_answer.join(", ") || "未作答"}</span></div>
                <div>参考答案：<span className="text-emerald-700 font-semibold">{d.correct_answer.join(", ")}</span></div>
                {d.ai_feedback && (
                  <div className="rounded-lg border border-yellow-300 bg-yellow-100 px-3 py-2">
                    <span className="font-extrabold text-yellow-900 text-lg">智能评语：</span>
                    <span className="text-gray-900 ml-1">{d.ai_feedback}</span>
                  </div>
                )}
                {d.explanation && <div className="text-gray-600">解析：{d.explanation}</div>}
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      <div className="mt-6 text-center">
        <Button onClick={onClose}>返回考试列表</Button>
      </div>
    </div>
  );
}
