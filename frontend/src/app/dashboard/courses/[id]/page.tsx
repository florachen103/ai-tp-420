"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { AskResponse, CourseDetail, KnowledgeDocument, Material } from "@/types/api";
import {
  Send,
  FileText,
  User,
  ChevronRight,
  RefreshCw,
  Map as MapIcon,
  MessageCircle,
  Loader2,
  Film,
  HelpCircle,
  Quote,
  AlertTriangle,
  Target,
  Scale,
  Repeat2,
  Timer,
  Users,
  MessageSquare,
  LayoutList,
  Puzzle,
  Handshake,
  BookOpen,
  ListChecks,
  SlidersHorizontal,
  ThumbsUp,
  ThumbsDown,
  CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { pickScenarioCards, type ScenarioIconName } from "@/lib/course-scenarios";
import { PARSE_STATUS_LABEL } from "@/lib/ui-labels";

interface Msg {
  role: "user" | "assistant";
  content: string;
  sources?: AskResponse["sources"];
  queriesUsed?: string[];
  answerId?: string;
  /** 本地记录当前 msg 的满意度状态，点过就不再可改 */
  feedback?: 1 | -1 | null;
  /** 差评时展示评语输入框 */
  showCommentInput?: boolean;
  commentDraft?: string;
}

type ResponseStyle = "micro" | "standard" | "deep";

function materialParsePercent(m: Material): number {
  if (m.parse_status === "parsed") return 100;
  if (m.parse_status === "failed") {
    const p = m.meta?.parse_progress;
    return typeof p === "number" ? Math.min(100, Math.max(0, p as number)) : 0;
  }
  if (m.parse_status === "pending") {
    const p = m.meta?.parse_progress;
    return typeof p === "number" ? Math.min(100, Math.max(0, p as number)) : 0;
  }
  const p = m.meta?.parse_progress;
  return typeof p === "number" ? Math.min(100, Math.max(0, p as number)) : 8;
}

/** 助手回复：话术引用块 + 二级标题（含「划重点」）扁平高亮 */
const TUTOR_MARKDOWN_COMPONENTS: Partial<Components> = {
  blockquote: ({ children }) => (
    <blockquote className="not-prose my-3 rounded-xl border border-sky-200/90 bg-sky-50 px-4 py-3.5 text-[0.9375rem] leading-relaxed text-gray-800 shadow-sm border-l-[3px] border-l-sky-500 [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0">
      {children}
    </blockquote>
  ),
  h2: ({ children, className, ...props }) => (
    <h2
      {...props}
      className={cn(
        "not-prose mt-5 mb-2.5 rounded-lg border border-brand-100 bg-brand-50/95 px-3 py-2 text-base font-semibold text-brand-900 tracking-tight",
        className
      )}
    >
      {children}
    </h2>
  ),
};

const SCENARIO_LUCIDE: Record<ScenarioIconName, ComponentType<{ className?: string }>> = {
  Film,
  HelpCircle,
  Quote,
  AlertTriangle,
  Target,
  Scale,
  Repeat2,
  Timer,
  Users,
  MessageSquare,
  LayoutList,
  Puzzle,
  Handshake,
  BookOpen,
  ListChecks,
  SlidersHorizontal,
};

const STYLE_OPTIONS: { id: ResponseStyle; label: string; hint: string }[] = [
  { id: "micro", label: "场景小口", hint: "短、轻快、像闯关" },
  { id: "standard", label: "条理适中", hint: "分点更清晰" },
  { id: "deep", label: "深度展开", hint: "允许写长一点" },
];

/** localStorage 里缓存对话的 key（按课程 id 分） */
function chatHistoryKey(courseId: number) {
  return `rag.chat.course.${courseId}`;
}
/** 序列化时把不需要跨会话持久的瞬态字段剥掉 */
function sanitizeForStorage(msgs: Msg[]): Msg[] {
  return msgs.map((m) => {
    const { showCommentInput: _s, commentDraft: _c, ...rest } = m;
    return rest;
  });
}

export default function CourseDetailPage({ params }: { params: { id: string } }) {
  const courseId = Number(params.id);
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [persona, setPersona] = useState("");
  const [question, setQuestion] = useState("");
  /**
   * 初值从 localStorage 恢复，保证刷新后对话历史不丢。
   * 服务端渲染时 window 不存在，所以用 lazy initializer + try/catch。
   */
  const [msgs, setMsgs] = useState<Msg[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      const raw = window.localStorage.getItem(chatHistoryKey(courseId));
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? (parsed as Msg[]) : [];
    } catch {
      return [];
    }
  });
  const [asking, setAsking] = useState(false);
  const [responseStyle, setResponseStyle] = useState<ResponseStyle>("micro");
  /** 场景小片段批次：递增则换一批随机场景 */
  const [scenarioBatch, setScenarioBatch] = useState(0);
  /** 检索范围：选中的课件 id。空集合 = 全课程检索 */
  const [scopeMaterialIds, setScopeMaterialIds] = useState<number[]>([]);
  /** 检索范围：章节精确匹配。空串 = 不限 */
  const [scopeChapter, setScopeChapter] = useState("");
  /** 该课程实际有内容的章节列表（来自后端 /courses/{id}/chapters） */
  const [chapterOptions, setChapterOptions] = useState<string[]>([]);
  const [knowledgeDocs, setKnowledgeDocs] = useState<KnowledgeDocument[]>([]);
  /** 是否启用查询改写（默认开，方便学员口语提问） */
  const [rewriteEnabled, setRewriteEnabled] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadCourse = useCallback(() => {
    api.get<CourseDetail>(`/courses/${courseId}`).then(setCourse);
  }, [courseId]);

  useEffect(() => {
    loadCourse();
  }, [loadCourse]);

  useEffect(() => {
    api
      .get<string[]>(`/courses/${courseId}/chapters`)
      .then((list) => setChapterOptions(list || []))
      .catch(() => setChapterOptions([]));
  }, [courseId]);

  useEffect(() => {
    if (!course?.knowledge_space_id) {
      setKnowledgeDocs([]);
      return;
    }
    api
      .get<KnowledgeDocument[]>(`/knowledge/documents?space_id=${course.knowledge_space_id}&status=published`)
      .then((list) => setKnowledgeDocs(list || []))
      .catch(() => setKnowledgeDocs([]));
  }, [course?.knowledge_space_id]);

  /**
   * 跨会话同步反馈状态：从后端拉 {answer_id: rating} 覆盖本地 msgs 里的 feedback 字段。
   * 防止 localStorage 和真实数据库状态不一致（例如管理员清了数据 / 用户换设备）。
   * 只在 courseId 变化时跑一次；后续点赞/差评由 submitFeedback 直接更新本地。
   */
  useEffect(() => {
    let cancelled = false;
    api
      .get<Record<string, number>>(`/courses/${courseId}/ask/feedback/mine`)
      .then((map) => {
        if (cancelled || !map) return;
        setMsgs((list) =>
          list.map((m) => {
            if (m.role !== "assistant" || !m.answerId) return m;
            const rating = map[m.answerId];
            if (rating === 1 || rating === -1) {
              return { ...m, feedback: rating as 1 | -1 };
            }
            return m;
          })
        );
      })
      .catch(() => {
        // 静默失败：反馈恢复只是锦上添花，不要打扰学员
      });
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  /** 每次对话变化都写回 localStorage，刷新或切换路由后能恢复 */
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(
        chatHistoryKey(courseId),
        JSON.stringify(sanitizeForStorage(msgs))
      );
    } catch {
      // 容量超限 / 隐私模式下 setItem 抛异常，忽略即可
    }
  }, [msgs, courseId]);

  const hasActiveParse = course?.materials?.some(
    (m) => m.parse_status === "pending" || m.parse_status === "parsing"
  );
  useEffect(() => {
    if (!hasActiveParse) return;
    const t = setInterval(loadCourse, 2500);
    return () => clearInterval(t);
  }, [hasActiveParse, loadCourse]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, asking]);

  const scenarios = useMemo(
    () => (course ? pickScenarioCards(course.title, course.description, scenarioBatch, 5) : []),
    [course, scenarioBatch]
  );
  const wikiDocIdByPath = useMemo(() => {
    const map = new Map<string, number>();
    for (const d of knowledgeDocs) {
      if (d.path_slug) map.set(d.path_slug, d.id);
    }
    return map;
  }, [knowledgeDocs]);

  const runAsk = useCallback(
    async (rawQuestion: string) => {
      const q = rawQuestion.trim();
      if (!q || asking) return;
      setMsgs((m) => [...m, { role: "user", content: q }]);
      setAsking(true);
      try {
        const res = await api.post<AskResponse>(`/courses/${courseId}/ask`, {
          question: q,
          persona: persona || undefined,
          top_k: responseStyle === "micro" ? 4 : 6,
          response_style: responseStyle,
          material_ids: scopeMaterialIds.length > 0 ? scopeMaterialIds : undefined,
          chapter: scopeChapter.trim() || undefined,
          rewrite: rewriteEnabled,
        });
        setMsgs((m) => [
          ...m,
          {
            role: "assistant",
            content: res.answer,
            sources: res.sources,
            queriesUsed: res.queries_used,
            answerId: res.answer_id,
            feedback: null,
          },
        ]);
      } catch (err) {
        const msg = err instanceof ApiError ? err.detail : "问答失败";
        toast.error(msg);
        setMsgs((m) => m.slice(0, -1));
      } finally {
        setAsking(false);
      }
    },
    [asking, courseId, persona, responseStyle, scopeMaterialIds, scopeChapter, rewriteEnabled]
  );

  async function ask() {
    await runAsk(question);
    setQuestion("");
  }

  /** 点击好评/差评时立即写回本地状态 + 上报；差评会打开评语输入区，提交评语再发一次覆盖式更新 */
  async function submitFeedback(msgIndex: number, rating: 1 | -1, comment?: string) {
    const msg = msgs[msgIndex];
    if (!msg || !msg.answerId) return;
    setMsgs((m) =>
      m.map((x, i) =>
        i === msgIndex
          ? {
              ...x,
              feedback: rating,
              showCommentInput: rating === -1,
              commentDraft: comment ?? x.commentDraft ?? "",
            }
          : x
      )
    );
    try {
      await api.post(`/courses/${courseId}/ask/feedback`, {
        answer_id: msg.answerId,
        rating,
        comment: comment && comment.trim() ? comment.trim() : undefined,
      });
      if (rating === 1) toast.success("感谢反馈");
      if (rating === -1 && comment !== undefined) toast.success("已记录，评语会帮助我们改进");
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : "反馈提交失败";
      toast.error(detail);
      // 回滚本地状态
      setMsgs((m) =>
        m.map((x, i) => (i === msgIndex ? { ...x, feedback: null } : x))
      );
    }
  }

  if (!course) return <div className="p-6 text-gray-500">加载中...</div>;

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto flex flex-col gap-5 pb-10">
      {/* 轻量头部：中性底 + 左侧细色条点题，减少大面积品牌色 */}
      <div className="rounded-2xl border border-gray-200/90 bg-white pl-4 pr-5 py-4 shadow-sm">
        <div className="border-l-[3px] border-brand-500 pl-3">
          <p className="text-xs font-normal text-gray-500 tracking-wide">今日学习路径</p>
          <h1 className="text-lg font-semibold text-gray-900 mt-0.5 leading-snug">{course.title}</h1>
          {course.description && (
            <p className="text-sm font-normal text-gray-600 mt-1.5 line-clamp-2 leading-relaxed">{course.description}</p>
          )}
          <p className="text-xs font-normal text-gray-500 mt-2 leading-relaxed">
            点下面小卡片，一次只学一口；想自己问也可以，在底部输入框发言。
          </p>
        </div>
      </div>

      {/* 回答风格 */}
      <div>
        <p className="text-xs text-gray-500 mb-2">助手回答长度</p>
        <div className="flex flex-wrap gap-2 p-1 rounded-xl bg-gray-50 border border-gray-100">
          {STYLE_OPTIONS.map((o) => (
            <button
              key={o.id}
              type="button"
              onClick={() => setResponseStyle(o.id)}
              className={cn(
                "flex-1 min-w-[5.5rem] rounded-lg px-3 py-2 text-left transition",
                responseStyle === o.id
                  ? "bg-white text-gray-900 shadow-sm ring-1 ring-brand-500/15 ring-inset"
                  : "text-gray-600 hover:text-gray-900 hover:bg-white/80"
              )}
            >
              <div className="text-sm font-medium">{o.label}</div>
              <div className="text-[11px] font-normal text-gray-500 leading-tight mt-0.5">{o.hint}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 场景小片段 */}
      <Card className="border border-gray-200 bg-gray-50/40 shadow-none">
        <CardBody className="!py-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-500" aria-hidden>
                <MapIcon className="h-4 w-4" />
              </span>
              场景小片段
              <span className="text-xs font-normal text-gray-500">点卡片开始；可换一批继续学</span>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="shrink-0 gap-1.5"
              disabled={asking}
              onClick={() => setScenarioBatch((n) => n + 1)}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              换一换
            </Button>
          </div>
          <div className="mt-3 flex gap-3 overflow-x-auto pb-1 snap-x snap-mandatory scrollbar-thin -mx-1 px-1">
            {scenarios.map((s) => {
              const ScenarioIcon = SCENARIO_LUCIDE[s.icon];
              return (
              <button
                key={s.id}
                type="button"
                disabled={asking}
                onClick={() => runAsk(s.question)}
                className={cn(
                  "snap-start shrink-0 w-[9.5rem] sm:w-[10.5rem] rounded-xl border border-gray-200 bg-white p-3 text-left shadow-sm",
                  "hover:border-gray-300 hover:bg-gray-50/80 active:scale-[0.99] transition disabled:opacity-50"
                )}
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
                  <ScenarioIcon className="h-5 w-5" />
                </div>
                <div className="mt-2 text-sm font-medium text-gray-900 leading-tight">{s.title}</div>
                <div className="text-[11px] font-normal text-gray-500 mt-1 leading-snug">{s.subtitle}</div>
                <div className="mt-2 flex items-center text-[11px] font-normal text-gray-500">
                  开始 <ChevronRight className="h-3 w-3 text-gray-400" />
                </div>
              </button>
            );
            })}
          </div>
        </CardBody>
      </Card>

      {/* 课件状态折叠，降低信息压力 */}
      {course.materials.length > 0 && (
        <details className="group rounded-xl border border-gray-100 bg-gray-50/50 text-sm">
          <summary className="cursor-pointer list-none px-4 py-3 flex items-center gap-2 text-gray-600">
            <FileText className="h-4 w-4 text-gray-400" />
            <span>课件与解析状态</span>
            <span className="text-xs text-gray-400">（{course.materials.length} 个文件）</span>
            <span className="ml-auto text-xs text-gray-500 group-open:hidden">展开</span>
            <span className="ml-auto text-xs text-gray-500 hidden group-open:inline">收起</span>
          </summary>
          <div className="px-4 pb-3 flex flex-wrap gap-2">
            {course.materials.map((m) => (
              <span
                key={m.id}
                className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg bg-white border border-gray-100 text-gray-600"
              >
                {m.filename}
                <span
                  className={
                    m.parse_status === "parsed"
                      ? "text-emerald-600"
                      : m.parse_status === "failed"
                        ? "text-rose-600"
                        : "text-amber-600"
                  }
                >
                  {PARSE_STATUS_LABEL[m.parse_status] ?? "处理中"} {materialParsePercent(m)}%
                </span>
              </span>
            ))}
          </div>
        </details>
      )}

      {/* 检索范围（课件/章节）+ 查询改写开关 */}
      {course.materials.length > 0 && (
        <details className="rounded-xl border border-gray-100">
          <summary className="cursor-pointer list-none px-4 py-3 text-sm text-gray-600 flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4" />
            检索范围（可选，限定问答知识面）
            <span className="ml-auto text-xs text-gray-400">
              {scopeMaterialIds.length > 0
                ? `仅 ${scopeMaterialIds.length} 份课件`
                : "全课程"}
              {scopeChapter.trim() ? ` · ${scopeChapter.trim()}` : ""}
            </span>
          </summary>
          <div className="px-4 pb-4 space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-xs text-gray-500">只问哪些课件（不勾 = 全部）</p>
                {scopeMaterialIds.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setScopeMaterialIds([])}
                    className="text-xs text-brand-600 hover:underline"
                  >
                    清空
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {course.materials.map((m) => {
                  const active = scopeMaterialIds.includes(m.id);
                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() =>
                        setScopeMaterialIds((prev) =>
                          prev.includes(m.id)
                            ? prev.filter((x) => x !== m.id)
                            : [...prev, m.id]
                        )
                      }
                      className={cn(
                        "text-xs px-2.5 py-1 rounded-lg border transition",
                        active
                          ? "bg-brand-50 border-brand-200 text-brand-800"
                          : "bg-white border-gray-200 text-gray-600 hover:border-gray-300"
                      )}
                    >
                      {m.filename}
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-xs text-gray-500">
                  章节过滤（选填，共 {chapterOptions.length} 个章节）
                </p>
                {scopeChapter && (
                  <button
                    type="button"
                    onClick={() => setScopeChapter("")}
                    className="text-xs text-brand-600 hover:underline"
                  >
                    清空
                  </button>
                )}
              </div>
              {chapterOptions.length > 0 ? (
                <select
                  value={scopeChapter}
                  onChange={(e) => setScopeChapter(e.target.value)}
                  className="w-full text-sm rounded-lg border border-gray-200 bg-white px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500/25"
                >
                  <option value="">全部章节</option>
                  {chapterOptions.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="text-xs text-gray-400 italic">
                  课件尚未解析出可选章节，暂无法按章节过滤。
                </div>
              )}
            </div>
            <label className="flex items-center gap-2 text-xs text-gray-600 select-none">
              <input
                type="checkbox"
                checked={rewriteEnabled}
                onChange={(e) => setRewriteEnabled(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              启用查询改写（把口语问题扩成同义短语，提高命中率）
            </label>
          </div>
        </details>
      )}

      <details className="rounded-xl border border-gray-100">
        <summary className="cursor-pointer list-none px-4 py-3 text-sm text-gray-600 flex items-center gap-2">
          <User className="h-4 w-4" />
          顾客画像（可选，让场景更贴脸）
          <span className="ml-auto text-xs text-gray-400">选填</span>
        </summary>
        <div className="px-4 pb-4">
          <Textarea
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
            placeholder="例如：30 岁女性，注重养生但怕麻烦…"
            rows={3}
            className="text-sm"
          />
        </div>
      </details>

      {/* 对话区 */}
      <Card className="flex-1 border border-gray-200 shadow-sm">
        <CardBody className="flex flex-col min-h-[52vh]">
          {msgs.length > 0 && (
            <div className="flex justify-end mb-2">
              <button
                type="button"
                onClick={() => {
                  if (!confirm("确定清空本课程对话记录？")) return;
                  setMsgs([]);
                  try {
                    window.localStorage.removeItem(chatHistoryKey(courseId));
                  } catch {
                    /* ignore */
                  }
                }}
                className="text-xs text-gray-400 hover:text-rose-600 transition"
              >
                清空对话
              </button>
            </div>
          )}
          <div className="flex-1 overflow-y-auto scrollbar-thin pr-1 space-y-3">
            {msgs.length === 0 && (
              <div className="h-full min-h-[220px] flex flex-col items-center justify-center text-center px-4 text-gray-400">
                <MessageCircle className="h-9 w-9 mb-2 text-gray-300" />
                <p className="text-sm font-medium text-gray-600">先点上面的「场景小片段」</p>
                <p className="text-xs font-normal text-gray-500 mt-1 max-w-xs leading-relaxed">
                  默认「场景小口」模式，助手会像闯关提示一样短答；需要长文再切到「深度展开」。
                </p>
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                <div
                  className={cn(
                    "max-w-[92%] rounded-2xl px-4 py-3 text-sm font-normal",
                    m.role === "user"
                      ? "bg-gray-800 text-gray-50 rounded-br-md"
                      : "bg-white text-gray-800 border border-gray-200 rounded-bl-md"
                  )}
                >
                  {m.role === "assistant" ? (
                    <div
                      className={cn(
                        "prose prose-sm prose-gray max-w-none font-normal leading-relaxed",
                        "[&_p]:my-2 [&_li]:my-1 [&_li]:leading-relaxed",
                        "[&_strong]:font-semibold [&_strong]:text-gray-900",
                        "[&_h3]:not-prose mt-3 mb-1.5 text-sm font-semibold text-gray-900",
                        "[&_ol]:list-decimal [&_ol]:pl-5 [&_ul]:list-disc [&_ul]:pl-5",
                        "[&_hr]:my-4 [&_hr]:border-gray-200"
                      )}
                    >
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={TUTOR_MARKDOWN_COMPONENTS}>
                        {m.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
                  )}
                  {m.role === "assistant" && m.answerId && (
                    <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-gray-200/80 pt-2">
                      <span className="text-xs text-gray-500">这次回答有帮助吗？</span>
                      <button
                        type="button"
                        onClick={() => submitFeedback(i, 1)}
                        disabled={m.feedback === 1}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs transition",
                          m.feedback === 1
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : "border-gray-200 bg-white text-gray-600 hover:border-emerald-300 hover:text-emerald-700"
                        )}
                        aria-label="好评"
                      >
                        {m.feedback === 1 ? (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        ) : (
                          <ThumbsUp className="h-3.5 w-3.5" />
                        )}
                        有用
                      </button>
                      <button
                        type="button"
                        onClick={() => submitFeedback(i, -1)}
                        disabled={m.feedback === -1 && !m.showCommentInput}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs transition",
                          m.feedback === -1
                            ? "border-rose-200 bg-rose-50 text-rose-700"
                            : "border-gray-200 bg-white text-gray-600 hover:border-rose-300 hover:text-rose-700"
                        )}
                        aria-label="差评"
                      >
                        <ThumbsDown className="h-3.5 w-3.5" />
                        没解决
                      </button>
                      {m.feedback === 1 && (
                        <span className="text-xs text-emerald-700">谢谢！已记录</span>
                      )}
                      {m.feedback === -1 && !m.showCommentInput && (
                        <span className="text-xs text-rose-600">已记录差评，欢迎再补一句评语</span>
                      )}
                    </div>
                  )}
                  {m.role === "assistant" && m.feedback === -1 && m.showCommentInput && (
                    <div className="mt-2 rounded-lg border border-rose-100 bg-rose-50/60 p-2">
                      <p className="text-xs text-rose-700 mb-1.5">
                        这段回答哪里不对？一句话描述一下就行
                      </p>
                      <Textarea
                        rows={2}
                        value={m.commentDraft ?? ""}
                        onChange={(e) =>
                          setMsgs((list) =>
                            list.map((x, idx) =>
                              idx === i ? { ...x, commentDraft: e.target.value } : x
                            )
                          )
                        }
                        placeholder="如：没回答到价格相关内容 / 引用了错误的章节…"
                        className="text-xs"
                      />
                      <div className="mt-1.5 flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            setMsgs((list) =>
                              list.map((x, idx) =>
                                idx === i
                                  ? { ...x, showCommentInput: false, commentDraft: "" }
                                  : x
                              )
                            )
                          }
                          className="text-xs text-gray-500 hover:text-gray-700"
                        >
                          不写了
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            const c = (m.commentDraft ?? "").trim();
                            submitFeedback(i, -1, c);
                            setMsgs((list) =>
                              list.map((x, idx) =>
                                idx === i ? { ...x, showCommentInput: false } : x
                              )
                            );
                          }}
                          className="rounded-md bg-rose-600 px-2 py-1 text-xs text-white hover:bg-rose-700"
                        >
                          提交评语
                        </button>
                      </div>
                    </div>
                  )}
                  {m.sources && m.sources.length > 0 && (
                    <details className="mt-2 text-xs text-gray-500 border-t border-gray-200/80 pt-2">
                      <summary className="cursor-pointer select-none">
                        参考了 {m.sources.length} 段课件（答案中的 [S1]…[S{m.sources.length}] 对应下列片段）
                      </summary>
                      <ul className="mt-1 space-y-1.5">
                        {[...m.sources]
                          .sort(
                            (a, b) =>
                              (b.citations ?? 0) - (a.citations ?? 0) || a.index - b.index
                          )
                          .map((s, si) => {
                            const wikiDocId = s.wiki_path ? wikiDocIdByPath.get(s.wiki_path) : undefined;
                            return (
                            <li key={si} className="pl-2 border-l-2 border-gray-200">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="inline-flex items-center justify-center min-w-[1.75rem] h-5 px-1 rounded bg-yellow-100 text-yellow-900 font-semibold text-[11px]">
                                  S{s.index ?? si + 1}
                                </span>
                                <span className="font-medium text-gray-600">
                                  {s.chapter || "片段"}
                                </span>
                                {(s.wiki_path || s.wiki_section) && (
                                  <span className="text-gray-500">
                                    · {s.wiki_path || "未命名页面"}{s.wiki_section ? ` / ${s.wiki_section}` : ""}
                                  </span>
                                )}
                                {s.wiki_path && wikiDocId && (
                                  <Link
                                    href={`/admin/knowledge/drafts/${wikiDocId}${s.wiki_section_anchor ? `#${s.wiki_section_anchor}` : ""}`}
                                    className="inline-flex items-center h-5 rounded-full bg-white px-2 text-[10px] font-medium text-brand-700 hover:bg-brand-50"
                                  >
                                    打开Wiki页面
                                  </Link>
                                )}
                                <span className="text-gray-400">
                                  · 相关度 {s.score.toFixed(2)}
                                </span>
                                {typeof s.citations === "number" && s.citations > 0 && (
                                  <span className="ml-1 inline-flex items-center h-5 px-1.5 rounded-full bg-brand-50 text-brand-700 text-[10px] font-medium">
                                    答案引用 {s.citations} 次
                                  </span>
                                )}
                                {s.citations === 0 && (
                                  <span className="ml-1 text-[10px] text-gray-400">未被引用</span>
                                )}
                              </div>
                              <p className="mt-0.5 text-gray-500 line-clamp-2">{s.snippet}</p>
                            </li>
                          );})}
                      </ul>
                      {m.queriesUsed && m.queriesUsed.length > 1 && (
                        <div className="mt-2 pt-2 border-t border-dashed border-gray-200/80">
                          <p className="text-[11px] text-gray-400 mb-1">本次检索用到的查询变体</p>
                          <div className="flex flex-wrap gap-1">
                            {m.queriesUsed.map((q, qi) => (
                              <span
                                key={qi}
                                className={cn(
                                  "text-[11px] px-1.5 py-0.5 rounded",
                                  qi === 0
                                    ? "bg-gray-100 text-gray-700"
                                    : "bg-sky-50 text-sky-700"
                                )}
                              >
                                {qi === 0 ? "原问题：" : ""}
                                {q}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </details>
                  )}
                </div>
              </div>
            ))}
            {asking && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-md px-4 py-3 text-sm bg-amber-50 text-amber-800 border border-amber-100">
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-amber-600" aria-hidden />
                    <span className="animate-pulse">正在编一小关</span>
                  </span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="mt-4 flex gap-2 border-t border-gray-50 pt-4">
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), ask())}
              placeholder="自己提问也可以，尽量一句话～"
              disabled={asking}
              className="rounded-xl"
            />
            <Button onClick={ask} disabled={asking || !question.trim()} className="rounded-xl shrink-0">
              <Send className="h-4 w-4" /> 发送
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
