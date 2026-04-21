"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import {
  AlertTriangle,
  BarChart3,
  Database,
  Quote,
  RefreshCw,
  Sparkles,
  Stethoscope,
  ThumbsDown,
  ThumbsUp,
  Trophy,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  AUDIT_RECOMMENDATION_AREA_BADGE,
  labelAuditRecommendationArea,
} from "@/lib/ui-labels";

interface DailyPoint {
  date: string;
  asks: number;
  cache_hits: number;
  with_citation: number;
  citation_removed: number;
}

interface RagMetrics {
  window_days: number;
  ask_count: number;
  cache_hit_rate: number;
  answers_with_citation_rate: number;
  avg_citations_per_answer: number;
  citation_removed_rate: number;
  top_courses: Array<{ course_id: number; title: string; ask_count: number }>;
  recent_questions: Array<{
    created_at: string | null;
    course_id: number | null;
    question: string;
    expansions: string[];
    citations_used: number[];
    citations_removed: number[];
    cache_hit: boolean;
  }>;
  daily_series: DailyPoint[];
  feedback: {
    total: number;
    good: number;
    bad: number;
    satisfaction_rate: number;
    coverage_rate: number;
    recent_bad: Array<{
      id: number;
      created_at: string | null;
      course_id: number | null;
      question: string;
      comment: string;
      citations_used: number[];
      cache_hit: boolean;
    }>;
    table_missing?: boolean;
  };
  index_health: {
    courses: number;
    materials: number;
    chunks: number;
    chunks_with_embedding: number;
    knowledge_spaces: number;
    knowledge_documents: number;
    published_documents: number;
    knowledge_chunks: number;
  };
}

const WINDOW_OPTIONS = [
  { id: 7, label: "近 7 天" },
  { id: 30, label: "近 30 天" },
  { id: 90, label: "近 90 天" },
];

function fmtPercent(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

interface PromptAuditReport {
  days: number;
  course_id: number | null;
  sample_size: number;
  patterns: Array<{ title?: string; count?: number; note?: string }>;
  recommendations: Array<{ area?: string; action?: string; reason?: string }>;
  examples: Array<{ idx?: number; why?: string }>;
  cases: Array<{
    idx: number;
    question: string;
    comment: string;
    has_citation: boolean;
    cache_hit: boolean;
    course_id: number | null;
    created_at: string | null;
  }>;
  error: string | null;
}

export default function RagMetricsPage() {
  const [days, setDays] = useState<number>(30);
  const [data, setData] = useState<RagMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [audit, setAudit] = useState<PromptAuditReport | null>(null);
  const [auditing, setAuditing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<RagMetrics>(`/admin/rag/metrics?days=${days}`);
      setData(res);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "加载失败";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [days]);

  const runAudit = useCallback(async () => {
    setAuditing(true);
    try {
      const res = await api.post<PromptAuditReport>(
        `/admin/rag/prompt_audit?days=${days}`
      );
      setAudit(res);
      if (res.error) {
        toast.info(res.error);
      } else {
        toast.success(`已分析 ${res.sample_size} 条差评，共 ${res.recommendations.length} 条建议`);
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "生成失败";
      toast.error(msg);
    } finally {
      setAuditing(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto flex flex-col gap-5 pb-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-brand-700">
            <BarChart3 className="h-5 w-5" />
            <span className="text-xs font-medium">知识库监控</span>
          </div>
          <h1 className="text-xl font-semibold text-gray-900 mt-1">知识问答质量面板</h1>
          <p className="text-sm text-gray-500 mt-1">
            观测答案引用命中率、缓存节省、索引健康度，定位需要优化的课程。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-gray-200 bg-white p-0.5">
            {WINDOW_OPTIONS.map((o) => (
              <button
                key={o.id}
                type="button"
                onClick={() => setDays(o.id)}
                className={cn(
                  "px-3 py-1.5 text-sm rounded-md transition",
                  days === o.id ? "bg-brand-50 text-brand-800 font-medium" : "text-gray-600 hover:text-gray-900"
                )}
              >
                {o.label}
              </button>
            ))}
          </div>
          <Button variant="secondary" size="sm" onClick={load} disabled={loading} className="gap-1.5">
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            刷新
          </Button>
        </div>
      </div>

      {!data && loading && <div className="text-sm text-gray-400">加载中…</div>}

      {data && data.feedback?.table_missing && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <div className="font-medium">答案反馈表还未初始化</div>
          <div className="mt-1 text-amber-800/90">
            请在后端环境完成一次数据库结构升级（与部署文档中的迁移步骤一致），初始化反馈相关表后再刷新本页。此前的其它指标仍然可用。
          </div>
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <MetricCard
              icon={<Quote className="h-4 w-4" />}
              title="提问次数"
              value={data.ask_count.toString()}
              hint={`近 ${data.window_days} 天`}
            />
            <MetricCard
              icon={<Sparkles className="h-4 w-4 text-emerald-600" />}
              title="答案带引用率"
              value={fmtPercent(data.answers_with_citation_rate)}
              hint={`均引用 ${data.avg_citations_per_answer} 段 / 条`}
              tone={data.answers_with_citation_rate >= 0.7 ? "good" : data.answers_with_citation_rate >= 0.4 ? "warn" : "bad"}
            />
            <MetricCard
              icon={<Zap className="h-4 w-4 text-amber-600" />}
              title="缓存命中率"
              value={fmtPercent(data.cache_hit_rate)}
              hint="命中=省一次大模型调用"
              tone={data.cache_hit_rate >= 0.2 ? "good" : "neutral"}
            />
            <MetricCard
              icon={<Trophy className="h-4 w-4 text-rose-600" />}
              title="非法引用率"
              value={fmtPercent(data.citation_removed_rate)}
              hint="越低越好"
              tone={data.citation_removed_rate <= 0.05 ? "good" : data.citation_removed_rate <= 0.15 ? "warn" : "bad"}
            />
            <MetricCard
              icon={<ThumbsUp className="h-4 w-4 text-brand-600" />}
              title="学员满意度"
              value={
                data.feedback.total > 0
                  ? fmtPercent(data.feedback.satisfaction_rate)
                  : "-"
              }
              hint={
                data.feedback.total > 0
                  ? `${data.feedback.good}赞 / ${data.feedback.bad}踩 · 覆盖 ${fmtPercent(data.feedback.coverage_rate)}`
                  : "暂无反馈"
              }
              tone={
                data.feedback.total === 0
                  ? "neutral"
                  : data.feedback.satisfaction_rate >= 0.8
                    ? "good"
                    : data.feedback.satisfaction_rate >= 0.6
                      ? "warn"
                      : "bad"
              }
            />
          </div>

          <Card>
            <CardBody>
              <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
                <BarChart3 className="h-4 w-4 text-gray-500" />
                每日提问趋势
                <span className="text-xs font-normal text-gray-400 ml-1">
                  （蓝柱 = 总提问；绿段 = 带引用；橙点连线 = 缓存命中率）
                </span>
              </div>
              <DailyChart series={data.daily_series} />
            </CardBody>
          </Card>

          <IndexHealthCard health={data.index_health} />

          <Card>
            <CardBody>
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
                  <Stethoscope className="h-4 w-4 text-gray-500" />
                  差评驱动的提示词自检报告
                  <span className="text-xs font-normal text-gray-400 ml-1">
                    （取近 {data.window_days} 天差评 → 用大模型归纳共性并给调整建议，每次分析调用 1 次大模型）
                  </span>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={runAudit}
                  disabled={auditing}
                  className="gap-1.5"
                >
                  {auditing ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      分析中…
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-3.5 w-3.5" />
                      {audit ? "重新生成报告" : "生成报告"}
                    </>
                  )}
                </Button>
              </div>
              {!audit && !auditing && (
                <p className="mt-3 text-sm text-gray-400">
                  点右上角「生成报告」后会列出共性模式和改进建议。
                </p>
              )}
              {audit?.error && (
                <p className="mt-3 text-sm text-amber-700 bg-amber-50 border border-amber-100 rounded-md px-3 py-2">
                  {audit.error}
                </p>
              )}
              {audit && !audit.error && (
                <AuditReport report={audit} />
              )}
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
                <Trophy className="h-4 w-4 text-gray-500" />
                提问最多的课程 Top 10
              </div>
              {data.top_courses.length === 0 ? (
                <p className="mt-3 text-sm text-gray-400">暂无提问数据</p>
              ) : (
                <ul className="mt-3 divide-y divide-gray-100">
                  {data.top_courses.map((c, i) => (
                    <li key={c.course_id} className="flex items-center justify-between py-2 text-sm">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-gray-100 text-gray-600 text-xs">
                          {i + 1}
                        </span>
                        <span className="truncate">{c.title}</span>
                      </div>
                      <span className="text-gray-500 shrink-0">{c.ask_count} 次</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
                <ThumbsDown className="h-4 w-4 text-rose-500" />
                最近 10 条差评
                <span className="text-xs font-normal text-gray-400 ml-1">
                  （优先排查：提示词是否偏、检索是否跑题、语料是否过期）
                </span>
              </div>
              {data.feedback.recent_bad.length === 0 ? (
                <p className="mt-3 text-sm text-gray-400">
                  暂无差评 —— 要么大家都很满意，要么还没人点
                </p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {data.feedback.recent_bad.map((r) => (
                    <li
                      key={r.id}
                      className="border border-rose-100 bg-rose-50/40 rounded-lg px-3 py-2.5 text-sm"
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-gray-900 font-medium">
                          {r.question || "（空）"}
                        </span>
                        {r.cache_hit && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700">
                            缓存命中
                          </span>
                        )}
                        {r.citations_used.length === 0 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-100 text-rose-700">
                            答案无引用
                          </span>
                        )}
                      </div>
                      {r.comment && (
                        <div className="mt-1 text-xs text-rose-800 italic whitespace-pre-wrap">
                          “{r.comment}”
                        </div>
                      )}
                      <div className="mt-1 text-[11px] text-gray-400">
                        {r.created_at ? new Date(r.created_at).toLocaleString() : ""}
                        {r.course_id ? ` · 课程 #${r.course_id}` : ""}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
                <Quote className="h-4 w-4 text-gray-500" />
                最近 20 次提问
                <span className="text-xs font-normal text-gray-400 ml-1">
                  （用于抽检改写质量与引用合规）
                </span>
              </div>
              {data.recent_questions.length === 0 ? (
                <p className="mt-3 text-sm text-gray-400">暂无提问数据</p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {data.recent_questions.map((r, i) => (
                    <li key={i} className="border border-gray-100 rounded-lg px-3 py-2.5 text-sm">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-gray-900 font-medium">{r.question || "（空）"}</span>
                        {r.cache_hit && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700">缓存命中</span>
                        )}
                        {r.citations_used.length > 0 ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700">
                            引用 {r.citations_used.length} 段
                          </span>
                        ) : (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">未引用</span>
                        )}
                        {r.citations_removed.length > 0 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-50 text-rose-700">
                            剥除 {r.citations_removed.length} 条非法
                          </span>
                        )}
                      </div>
                      {r.expansions.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {r.expansions.map((e, ei) => (
                            <span key={ei} className="text-[11px] px-1.5 py-0.5 rounded bg-sky-50 text-sky-700">
                              {e}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="mt-1 text-[11px] text-gray-400">
                        {r.created_at ? new Date(r.created_at).toLocaleString() : ""}
                        {r.course_id ? ` · 课程 #${r.course_id}` : ""}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}

function MetricCard({
  icon,
  title,
  value,
  hint,
  tone = "neutral",
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
  hint?: string;
  tone?: "good" | "warn" | "bad" | "neutral";
}) {
  const toneClass = {
    good: "text-emerald-700",
    warn: "text-amber-700",
    bad: "text-rose-700",
    neutral: "text-gray-900",
  }[tone];
  return (
    <Card>
      <CardBody>
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          {icon}
          <span>{title}</span>
        </div>
        <div className={cn("mt-1.5 text-2xl font-semibold", toneClass)}>{value}</div>
        {hint && <div className="text-[11px] text-gray-500 mt-0.5">{hint}</div>}
      </CardBody>
    </Card>
  );
}

function HealthItem({
  label,
  value,
  sub,
  accent = "good",
}: {
  label: string;
  value: number;
  sub?: string;
  accent?: "good" | "warn" | "bad";
}) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50/60 px-3 py-2">
      <div className="text-xs text-gray-500">{label}</div>
      <div
        className={cn(
          "text-lg font-semibold mt-0.5",
          accent === "bad"
            ? "text-rose-700"
            : accent === "warn"
              ? "text-amber-700"
              : "text-gray-900"
        )}
      >
        {value.toLocaleString()}
      </div>
      {sub && <div className="text-[11px] text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}

/**
 * 索引健康度卡片，带三档告警：
 *   - 向量覆盖率 < 95%：黄条提示可能有课件还在处理中 / 向量化失败
 *   - chunks === 0：红条提示知识库为空，此时问答必然无法基于课件回答
 *   - 一切正常：绿色 pulse 点
 */
function IndexHealthCard({
  health,
}: {
  health: RagMetrics["index_health"];
}) {
  const coverage =
    health.chunks > 0 ? health.chunks_with_embedding / health.chunks : 0;
  const isEmpty = health.chunks === 0;
  const lowCoverage = !isEmpty && coverage < 0.95;
  const missing = Math.max(0, health.chunks - health.chunks_with_embedding);

  const banner = isEmpty
    ? {
        tone: "bad" as const,
        title: "知识库当前为空",
        detail:
          "还没有任何切片入库，学员此刻的提问都会走到「无引用」路径。去「管理后台 → 课程」上传并解析课件。",
      }
    : lowCoverage
      ? {
          tone: "warn" as const,
          title: `向量覆盖率 ${fmtPercent(coverage)}（低于 95%）`,
          detail: `有 ${missing} 个切片还没生成向量。可能原因：课件正在解析中、向量生成服务临时失败、向量维度与模型不匹配。建议进入管理后台对解析失败的课件点「重新解析」。`,
        }
      : null;

  return (
    <Card>
      <CardBody>
        <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
          <Database className="h-4 w-4 text-gray-500" />
          索引健康度
          {!banner && (
            <span className="relative flex h-2 w-2 ml-1" title="一切正常">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
          )}
        </div>

        {banner && (
          <div
            className={cn(
              "mt-3 flex items-start gap-2 rounded-lg px-3 py-2.5 text-sm border",
              banner.tone === "bad"
                ? "bg-rose-50 border-rose-200 text-rose-900"
                : "bg-amber-50 border-amber-200 text-amber-900"
            )}
          >
            <AlertTriangle
              className={cn(
                "h-4 w-4 mt-0.5 shrink-0",
                banner.tone === "bad" ? "text-rose-500" : "text-amber-500"
              )}
            />
            <div className="min-w-0">
              <div className="font-medium">{banner.title}</div>
              <div
                className={cn(
                  "text-xs mt-0.5",
                  banner.tone === "bad" ? "text-rose-800/90" : "text-amber-800/90"
                )}
              >
                {banner.detail}
              </div>
            </div>
          </div>
        )}

        <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <HealthItem label="课程数" value={health.courses} />
          <HealthItem label="课件数" value={health.materials} />
          <HealthItem label="知识空间" value={health.knowledge_spaces} />
          <HealthItem label="知识页" value={health.knowledge_documents} />
          <HealthItem
            label="知识切片"
            value={health.chunks}
            accent={isEmpty ? "bad" : "good"}
          />
          <HealthItem
            label="已向量化"
            value={health.chunks_with_embedding}
            accent={isEmpty ? "bad" : lowCoverage ? "warn" : "good"}
            sub={
              health.chunks > 0
                ? `${fmtPercent(coverage)} 覆盖`
                : undefined
            }
          />
          <HealthItem label="已发布页" value={health.published_documents} />
          <HealthItem label="发布后切片" value={health.knowledge_chunks} />
        </div>
      </CardBody>
    </Card>
  );
}

/** 把大模型输出的 patterns / recommendations / examples 渲染成可读的报告卡 */
function AuditReport({ report }: { report: PromptAuditReport }) {
  const caseByIdx = new Map<number, (typeof report.cases)[number]>();
  report.cases.forEach((c) => caseByIdx.set(c.idx, c));

  return (
    <div className="mt-3 space-y-5">
      <p className="text-xs text-gray-500">
        分析样本：<span className="text-gray-800 font-medium">{report.sample_size} 条差评</span>
        {report.course_id != null && (
          <span className="ml-1 text-gray-500">· 课程 #{report.course_id}</span>
        )}
      </p>

      {report.patterns.length > 0 && (
        <div>
          <div className="text-sm font-medium text-gray-800 mb-2">共性模式</div>
          <ul className="space-y-2">
            {report.patterns.map((p, i) => (
              <li
                key={i}
                className="border border-gray-100 rounded-lg px-3 py-2 text-sm"
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-900">
                    {p.title || "（未命名模式）"}
                  </span>
                  {typeof p.count === "number" && p.count > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                      {p.count} 条
                    </span>
                  )}
                </div>
                {p.note && (
                  <div className="text-xs text-gray-600 mt-0.5">{p.note}</div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.recommendations.length > 0 && (
        <div>
          <div className="text-sm font-medium text-gray-800 mb-2">改进建议</div>
          <ul className="space-y-2">
            {report.recommendations.map((r, i) => {
              const area =
                r.area && AUDIT_RECOMMENDATION_AREA_BADGE[r.area]
                  ? AUDIT_RECOMMENDATION_AREA_BADGE[r.area]
                  : null;
              return (
                <li
                  key={i}
                  className="border border-brand-100 bg-brand-50/40 rounded-lg px-3 py-2.5 text-sm"
                >
                  <div className="flex items-start gap-2">
                    <span
                      className={cn(
                        "text-[10px] px-1.5 py-0.5 rounded border font-medium shrink-0 mt-0.5",
                        area?.className ?? "bg-gray-50 text-gray-600 border-gray-200"
                      )}
                    >
                      {area?.label ?? labelAuditRecommendationArea(r.area)}
                    </span>
                    <div className="min-w-0">
                      <div className="text-gray-900">{r.action || "—"}</div>
                      {r.reason && (
                        <div className="text-xs text-gray-600 mt-1">
                          <span className="text-gray-500">依据：</span>
                          {r.reason}
                        </div>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {report.examples.length > 0 && (
        <div>
          <div className="text-sm font-medium text-gray-800 mb-2">代表性案例</div>
          <ul className="space-y-2">
            {report.examples.map((ex, i) => {
              const c = typeof ex.idx === "number" ? caseByIdx.get(ex.idx) : null;
              if (!c) return null;
              return (
                <li
                  key={i}
                  className="border border-rose-100 bg-rose-50/40 rounded-lg px-3 py-2.5 text-sm"
                >
                  <div className="text-gray-900 font-medium">{c.question || "（空问题）"}</div>
                  {c.comment && (
                    <div className="text-xs text-rose-800 italic mt-1 whitespace-pre-wrap">
                      “{c.comment}”
                    </div>
                  )}
                  {ex.why && (
                    <div className="text-xs text-gray-600 mt-1">
                      <span className="text-gray-500">为何代表：</span>
                      {ex.why}
                    </div>
                  )}
                  <div className="mt-1 flex flex-wrap gap-2 text-[10px]">
                    {!c.has_citation && (
                      <span className="px-1.5 py-0.5 rounded bg-rose-100 text-rose-700">
                        无引用
                      </span>
                    )}
                    {c.cache_hit && (
                      <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700">
                        缓存命中
                      </span>
                    )}
                    {c.course_id != null && (
                      <span className="text-gray-400">课程 #{c.course_id}</span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {report.patterns.length === 0 &&
        report.recommendations.length === 0 &&
        report.examples.length === 0 && (
          <p className="text-sm text-gray-400">大模型未产出结构化结论，可换个时间窗口再试。</p>
        )}
    </div>
  );
}

/**
 * 纯 SVG 折线 + 叠加柱状图：为了不引额外依赖（recharts 等）。
 * - 背景柱高 = 当日总提问数 (asks)
 * - 前景柱高 = 当日带引用的答案数 (with_citation)
 * - 折线 = 当日缓存命中率（0~1，右轴隐式用百分比）
 * 数据点 hover 时通过 title 显示 tooltip，足够用。
 */
function DailyChart({ series }: { series: DailyPoint[] }) {
  if (!series || series.length === 0) {
    return <p className="mt-3 text-sm text-gray-400">暂无趋势数据</p>;
  }
  const W = 720;
  const H = 180;
  const padL = 28;
  const padR = 12;
  const padT = 14;
  const padB = 24;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const maxAsks = Math.max(1, ...series.map((p) => p.asks));
  const n = series.length;
  const barW = Math.max(2, (innerW / n) * 0.7);
  const step = innerW / Math.max(1, n);

  // 折线：缓存命中率 (hits / asks)；当日无提问时画在底部
  const linePts = series.map((p, i) => {
    const rate = p.asks > 0 ? p.cache_hits / p.asks : 0;
    const x = padL + step * i + step / 2;
    const y = padT + innerH - rate * innerH;
    return { x, y, rate, p, i };
  });

  // 5 等分 y 轴标签（基于最大提问数）
  const ticks = 4;
  const yTickVals = Array.from({ length: ticks + 1 }, (_, k) => Math.round((maxAsks * k) / ticks));

  // x 轴仅显示首、中、尾三个日期，避免重叠
  const labelIndices = new Set<number>([0, Math.floor(n / 2), n - 1]);

  const linePath = linePts
    .map((pt, i) => `${i === 0 ? "M" : "L"}${pt.x.toFixed(1)},${pt.y.toFixed(1)}`)
    .join(" ");

  return (
    <div className="mt-3">
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-44 min-w-[640px]"
          preserveAspectRatio="none"
        >
          {/* 水平网格 */}
          {yTickVals.map((v, i) => {
            const y = padT + innerH - (v / Math.max(1, maxAsks)) * innerH;
            return (
              <g key={i}>
                <line
                  x1={padL}
                  x2={W - padR}
                  y1={y}
                  y2={y}
                  stroke="#f3f4f6"
                  strokeWidth={1}
                />
                <text
                  x={padL - 4}
                  y={y + 3}
                  fontSize={10}
                  fill="#9ca3af"
                  textAnchor="end"
                >
                  {v}
                </text>
              </g>
            );
          })}

          {/* 柱状图 */}
          {series.map((p, i) => {
            const x = padL + step * i + (step - barW) / 2;
            const hAsk = (p.asks / maxAsks) * innerH;
            const hCite = (p.with_citation / maxAsks) * innerH;
            const yAsk = padT + innerH - hAsk;
            const yCite = padT + innerH - hCite;
            return (
              <g key={p.date}>
                <title>
                  {`${p.date}\n提问 ${p.asks} · 带引用 ${p.with_citation} · 命中 ${p.cache_hits} · 剥除 ${p.citation_removed}`}
                </title>
                <rect
                  x={x}
                  y={yAsk}
                  width={barW}
                  height={Math.max(0, hAsk)}
                  rx={1}
                  fill="#dbeafe"
                />
                {p.with_citation > 0 && (
                  <rect
                    x={x}
                    y={yCite}
                    width={barW}
                    height={Math.max(0, hCite)}
                    rx={1}
                    fill="#22c55e"
                    opacity={0.75}
                  />
                )}
              </g>
            );
          })}

          {/* 缓存命中率折线 */}
          <path
            d={linePath}
            fill="none"
            stroke="#f59e0b"
            strokeWidth={1.5}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          {linePts.map((pt) => (
            <circle key={pt.p.date} cx={pt.x} cy={pt.y} r={2} fill="#f59e0b">
              <title>{`${pt.p.date} 缓存命中率 ${(pt.rate * 100).toFixed(1)}%`}</title>
            </circle>
          ))}

          {/* x 轴标签 */}
          {series.map((p, i) => {
            if (!labelIndices.has(i)) return null;
            const x = padL + step * i + step / 2;
            const short = p.date.slice(5); // MM-DD
            return (
              <text
                key={`xl-${p.date}`}
                x={x}
                y={H - 6}
                fontSize={10}
                fill="#9ca3af"
                textAnchor="middle"
              >
                {short}
              </text>
            );
          })}
        </svg>
      </div>
      <div className="flex flex-wrap gap-4 text-xs text-gray-500 mt-2 pl-7">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-sm bg-[#dbeafe]" />
          总提问
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-sm bg-[#22c55e]/80" />
          带引用
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-sm bg-[#f59e0b]" />
          缓存命中率
        </span>
      </div>
    </div>
  );
}
