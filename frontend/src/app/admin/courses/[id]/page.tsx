"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { CourseDetail, Exam, Material, Question } from "@/types/api";
import { FileText, Sparkles, ClipboardList, Upload, Trash2, RefreshCw, CheckCircle2, Eraser } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { ProgressBar } from "@/components/ui/progress-bar";
import { labelMaterialType, labelMaterialParseLine, labelQuestionDifficulty, labelQuestionType } from "@/lib/ui-labels";

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

export default function AdminCourseDetail({ params }: { params: { id: string } }) {
  const courseId = Number(params.id);
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [exams, setExams] = useState<Exam[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genPct, setGenPct] = useState<number | null>(null);
  const [genCount, setGenCount] = useState(10);
  const [creatingExam, setCreatingExam] = useState(false);
  const [examForm, setExamForm] = useState({ title: "", duration: 5, pass: 80 });
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);
  const [editingQuestionForm, setEditingQuestionForm] = useState({
    stem: "",
    optionsText: "",
    answerText: "",
    explanation: "",
    knowledgePointsText: "",
  });
  const [savingQuestion, setSavingQuestion] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadAll = useCallback(async () => {
    const [c, qs, es] = await Promise.all([
      api.get<CourseDetail>(`/courses/${courseId}`),
      api.get<Question[]>(`/questions?course_id=${courseId}`).catch(() => [] as Question[]),
      api.get<Exam[]>(`/exams?course_id=${courseId}`),
    ]);
    setCourse(c);
    setQuestions(qs);
    setExams(es);
  }, [courseId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    // 默认给出“课件题目”，管理员可继续修改
    if (!course) return;
    setExamForm((prev) => (prev.title.trim() ? prev : { ...prev, title: `${course.title}课件题目` }));
  }, [course]);

  const hasActiveParse = course?.materials?.some(
    (m) => m.parse_status === "pending" || m.parse_status === "parsing"
  );

  useEffect(() => {
    if (!hasActiveParse) return;
    const t = setInterval(() => loadAll(), 2500);
    return () => clearInterval(t);
  }, [hasActiveParse, loadAll]);

  async function onUpload(file: File) {
    setUploading(true);
    setUploadPct(0);
    try {
      await api.upload(`/courses/${courseId}/materials`, file, (p) => setUploadPct(p));
      toast.success(`已上传 ${file.name}，后台解析中...`);
      loadAll();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "上传失败";
      toast.error(msg);
    } finally {
      setUploading(false);
      setUploadPct(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function generateQuestions() {
    const targetTotal = genCount;
    const currentTotal = questions.length;
    const needGenerate = Math.max(0, targetTotal - currentTotal);
    if (needGenerate === 0) {
      toast.info(`当前题库已有 ${currentTotal} 题，已达到（或超过）目标总数 ${targetTotal}`);
      return;
    }

    setGenerating(true);
    setGenPct(6);
    const tick = setInterval(() => {
      setGenPct((p) => (p == null ? 8 : Math.min(90, p + 5)));
    }, 500);
    try {
      const res = await api.post<Question[]>(`/questions/course/${courseId}/generate`, {
        count: needGenerate,
      });
      setGenPct(100);
      toast.success(`已生成 ${res.length} 道题，题库总数目标 ${targetTotal} 题`);
      loadAll();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "生成失败";
      toast.error(msg);
    } finally {
      clearInterval(tick);
      setGenerating(false);
      setGenPct(null);
    }
  }

  async function reparseMaterial(materialId: number) {
    try {
      await api.post(`/courses/${courseId}/materials/${materialId}/reparse`);
      toast.success("已开始重新解析，请稍候刷新状态");
      loadAll();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "触发失败";
      toast.error(msg);
    }
  }

  async function createExam() {
    if (!examForm.title.trim()) return;
    setCreatingExam(true);
    try {
      await api.post("/exams", {
        course_id: courseId,
        title: examForm.title,
        duration_minutes: examForm.duration,
        pass_score: examForm.pass,
        rules: {
          single:   { count: 6, score: 5 },
          multiple: { count: 2, score: 10 },
          judge:    { count: 3, score: 5 },
          short:    { count: 1, score: 15 },
        },
      });
      toast.success("考试已创建");
      setExamForm((prev) => ({ ...prev, title: "", duration: 5, pass: 80 }));
      loadAll();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "创建失败";
      toast.error(msg);
    } finally {
      setCreatingExam(false);
    }
  }

  function startEditQuestion(q: Question) {
    const optionsText = (q.options || [])
      .map((o) => `${o.key}. ${o.text}`)
      .join("\n");
    setEditingQuestionId(q.id);
    setEditingQuestionForm({
      stem: q.stem || "",
      optionsText,
      answerText: (q.answer || []).join(", "),
      explanation: q.explanation || "",
      knowledgePointsText: (q.knowledge_points || []).join(", "),
    });
  }

  function parseOptionsText(text: string): Array<{ key: string; text: string }> {
    return text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line, idx) => {
        const m = line.match(/^([A-Za-z])[\.\)\-、:\s]+(.+)$/);
        if (m) return { key: m[1].toUpperCase(), text: m[2].trim() };
        const fallbackKey = String.fromCharCode(65 + idx);
        return { key: fallbackKey, text: line };
      });
  }

  async function saveQuestionEdit(q: Question) {
    if (!editingQuestionId || editingQuestionId !== q.id) return;
    if (!editingQuestionForm.stem.trim()) {
      toast.error("题干不能为空");
      return;
    }
    setSavingQuestion(true);
    try {
      await api.patch(`/questions/${q.id}`, {
        stem: editingQuestionForm.stem.trim(),
        options: parseOptionsText(editingQuestionForm.optionsText),
        answer: editingQuestionForm.answerText
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        explanation: editingQuestionForm.explanation.trim() || null,
        knowledge_points: editingQuestionForm.knowledgePointsText
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      toast.success("题目已更新");
      setEditingQuestionId(null);
      loadAll();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "保存失败";
      toast.error(msg);
    } finally {
      setSavingQuestion(false);
    }
  }

  if (!course) return <div className="p-6 text-gray-500">加载中...</div>;

  const activeMaterials = course.materials.filter(
    (m) => m.parse_status === "pending" || m.parse_status === "parsing"
  );
  const parseOverallPct =
    activeMaterials.length === 0
      ? null
      : Math.round(
          activeMaterials.reduce((s, m) => s + materialParsePercent(m), 0) / activeMaterials.length
        );

  const totalChunks = course.materials.reduce((n, m) => {
    const c = m.meta?.chunks;
    return n + (typeof c === "number" ? c : 0);
  }, 0);
  const canGenerateQuestions =
    course.materials.length > 0 &&
    course.materials.every((m) => m.parse_status === "parsed") &&
    totalChunks > 0;

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-gray-900">{course.title}</h1>
          <p className="text-sm text-gray-500">{course.description}</p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={async () => {
            if (!confirm("确定清空该课程的答案缓存吗？下次提问会重新调用大模型生成。")) return;
            try {
              await api.post(`/admin/rag/cache/clear?course_id=${courseId}`);
              toast.success("已清空该课程的答案缓存");
            } catch (err) {
              toast.error(err instanceof ApiError ? err.detail : "清空失败");
            }
          }}
          className="shrink-0 gap-1"
          title="让该课程的所有智能问答缓存立刻失效（调整提示词或修正语料时很有用）"
        >
          <Eraser className="h-4 w-4" />
          清空答案缓存
        </Button>
      </div>

      {hasActiveParse && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 space-y-3">
          <div className="flex items-start gap-3">
            <span className="relative flex h-3 w-3 shrink-0 mt-1">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500" />
            </span>
            <div className="flex-1 min-w-0">
              <span className="font-medium">课件正在后台解析</span>
              <span className="text-amber-800/90">（约 30 秒～2 分钟，取决于文件大小与向量化速度）</span>
              <div className="text-xs text-amber-800/80 mt-0.5">本页每 2.5 秒自动刷新进度，无需手动刷新。</div>
            </div>
          </div>
          {parseOverallPct != null && (
            <ProgressBar
              value={parseOverallPct}
              className="max-w-xl"
              label={`进行中课件平均进度（${activeMaterials.length} 个文件）`}
            />
          )}
        </div>
      )}

      {/* 课件管理 */}
      <Card>
        <CardBody>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <FileText className="h-4 w-4" /> 课件文件
            </h2>
            <div className="flex items-center gap-2">
              <input
                ref={fileRef}
                type="file"
                accept=".doc,.docx,.pdf,.ppt,.pptx,.xls,.xlsx,.csv,.md,.txt,.mp4,.mp3"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
              />
              <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
                <Upload className="h-4 w-4" />{" "}
                {uploading && uploadPct != null ? `上传中 ${uploadPct}%` : uploading ? "上传中…" : "上传课件"}
              </Button>
              <Button variant="secondary" size="sm" onClick={loadAll}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </div>
          {uploadPct != null && (
            <div className="mb-4 max-w-md">
              <ProgressBar value={uploadPct} label="上传到服务器" />
            </div>
          )}
          {course.materials.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-6">
              暂无课件。支持：文稿、PDF、演示稿、表格、视频、音频等（后续可接入语音识别）
            </p>
          ) : (
            <ul className="divide-y divide-gray-50">
              {course.materials.map((m) => (
                <li key={m.id} className="py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-sm">
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div className="h-8 w-8 rounded bg-brand-50 text-brand-600 flex items-center justify-center text-[10px] font-medium leading-tight text-center px-0.5 shrink-0">
                      {labelMaterialType(m.material_type)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium text-gray-900 truncate">{m.filename}</div>
                      <div className="text-xs text-gray-500">
                        {(m.size_bytes / 1024).toFixed(1)} KB · {formatDate(m.created_at)} ·
                        <span className={
                          m.parse_status === "parsed" ? "text-emerald-600 ml-1"
                            : m.parse_status === "failed" ? "text-rose-600 ml-1"
                            : "text-amber-600 ml-1"
                        }>{labelMaterialParseLine(m.meta, m.parse_status)}</span>
                        {typeof m.meta?.chunks === "number" && (
                          <span className="ml-2 text-gray-400">{m.meta.chunks as number} 切片</span>
                        )}
                      </div>
                      <div className="mt-2 max-w-md">
                        <ProgressBar
                          value={materialParsePercent(m)}
                          label={m.parse_status === "parsed" ? "解析与索引（已完成）" : "解析与索引"}
                        />
                      </div>
                      {m.parse_error && <div className="text-xs text-rose-500 mt-0.5">错误：{m.parse_error}</div>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {(m.parse_status === "pending" || m.parse_status === "parsing" || m.parse_status === "failed") && (
                      <Button variant="secondary" size="sm" className="!h-8 !px-2 text-xs" onClick={() => reparseMaterial(m.id)}>
                        重新解析
                      </Button>
                    )}
                    <button
                      className="text-gray-400 hover:text-rose-500 p-1"
                      onClick={async () => {
                        if (!confirm(`删除 ${m.filename}?`)) return;
                        await api.del(`/courses/${courseId}/materials/${m.id}`);
                        loadAll();
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      {/* 智能生成题目 */}
      <Card>
        <CardBody>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <Sparkles className="h-4 w-4" /> 题库（{questions.length} 题）
            </h2>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                className="w-20"
                min={1} max={50}
                value={genCount}
                onChange={(e) => setGenCount(Math.max(1, Math.min(50, Number(e.target.value) || 10)))}
              />
              <Button onClick={generateQuestions} disabled={generating || !canGenerateQuestions}>
                {generating && genPct != null ? `生成中 ${genPct}%` : generating ? "生成中…" : "智能生成题目"}
              </Button>
            </div>
          </div>
          {genPct != null && (
            <div className="mb-3 max-w-md">
              <ProgressBar value={genPct} label="智能出题（估算进度，完成后会刷新列表）" />
            </div>
          )}
          {!canGenerateQuestions && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 mb-3">
              生成题目前需：至少一份课件状态为「解析完成」，且知识切片数大于 0。
              {totalChunks === 0 && course.materials.some((m) => m.parse_status === "parsed") && " 若已显示解析完成但切片为 0，可能是 PDF 无可选文字层，请换可复制文字的文档。"}
            </p>
          )}
          {questions.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-6">
              尚未生成题目。上传课件后等待状态变为「解析完成」，再点「智能生成题目」。
            </p>
          ) : (
            <ul className="space-y-2 max-h-[480px] overflow-y-auto scrollbar-thin pr-1">
              {questions.slice(0, 50).map((q, i) => (
                <li key={q.id} className="p-3 rounded border border-gray-100 text-sm">
                  <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
                    <span>#{i + 1}</span>
                    <span className="px-1.5 py-0.5 bg-gray-100 rounded">{labelQuestionType(q.type)}</span>
                    <span className="px-1.5 py-0.5 bg-gray-100 rounded">{labelQuestionDifficulty(q.difficulty)}</span>
                    {q.reviewed && (
                      <span className="inline-flex items-center gap-0.5 text-emerald-600">
                        <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden />
                        已审核
                      </span>
                    )}
                  </div>
                  {editingQuestionId === q.id ? (
                    <div className="mt-2 space-y-2">
                      <Input
                        value={editingQuestionForm.stem}
                        onChange={(e) => setEditingQuestionForm((f) => ({ ...f, stem: e.target.value }))}
                        placeholder="题干"
                      />
                      <textarea
                        className="w-full min-h-[96px] rounded-lg border border-gray-200 p-3 text-sm"
                        value={editingQuestionForm.optionsText}
                        onChange={(e) => setEditingQuestionForm((f) => ({ ...f, optionsText: e.target.value }))}
                        placeholder="选项（每行一个，如：A. xxx）"
                      />
                      <Input
                        value={editingQuestionForm.answerText}
                        onChange={(e) => setEditingQuestionForm((f) => ({ ...f, answerText: e.target.value }))}
                        placeholder="答案（逗号分隔，如：A, C）"
                      />
                      <Input
                        value={editingQuestionForm.knowledgePointsText}
                        onChange={(e) => setEditingQuestionForm((f) => ({ ...f, knowledgePointsText: e.target.value }))}
                        placeholder="知识点（逗号分隔）"
                      />
                      <textarea
                        className="w-full min-h-[72px] rounded-lg border border-gray-200 p-3 text-sm"
                        value={editingQuestionForm.explanation}
                        onChange={(e) => setEditingQuestionForm((f) => ({ ...f, explanation: e.target.value }))}
                        placeholder="解析"
                      />
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => saveQuestionEdit(q)} disabled={savingQuestion}>
                          {savingQuestion ? "保存中..." : "保存"}
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => setEditingQuestionId(null)}>
                          取消
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="text-gray-900">{q.stem}</div>
                      {q.options.length > 0 && (
                        <ul className="mt-2 text-xs text-gray-600 space-y-0.5">
                          {q.options.map((o) => <li key={o.key}>{o.key}. {o.text}</li>)}
                        </ul>
                      )}
                      <div className="mt-2 text-xs text-gray-500">
                        答案：<span className="text-emerald-700">{q.answer?.join(", ")}</span>
                        {q.explanation && <span className="ml-3">解析：{q.explanation}</span>}
                      </div>
                      <div className="mt-2">
                        <Button size="sm" variant="secondary" onClick={() => startEditQuestion(q)}>
                          编辑题目
                        </Button>
                      </div>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      {/* 考试管理 */}
      <Card>
        <CardBody>
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <ClipboardList className="h-4 w-4" /> 考试
          </h2>
          <div className="grid md:grid-cols-3 gap-2 mb-4">
            <Input
              placeholder="考试名称"
              value={examForm.title}
              onChange={(e) => setExamForm({ ...examForm, title: e.target.value })}
            />
            <Input
              type="number" placeholder="时长(分钟)"
              value={examForm.duration}
              onChange={(e) => setExamForm({ ...examForm, duration: Number(e.target.value) || 5 })}
            />
            <div className="grid grid-cols-[1fr_auto] items-center gap-2">
              <Input
                type="number" placeholder="及格分"
                value={examForm.pass}
                onChange={(e) => setExamForm({ ...examForm, pass: Number(e.target.value) || 80 })}
              />
              <Button onClick={createExam} disabled={creatingExam} className="whitespace-nowrap">
                创建
              </Button>
            </div>
          </div>
          {exams.length === 0 ? (
            <p className="text-sm text-gray-500">还没有考试</p>
          ) : (
            <ul className="space-y-2">
              {exams.map((e) => (
                <li key={e.id} className="p-3 rounded border border-gray-100 flex justify-between items-center text-sm">
                  <div>
                    <div className="font-medium text-gray-900">{e.title}</div>
                    <div className="text-xs text-gray-500">
                      时长 {e.duration_minutes} 分钟 · 合格分 {e.pass_score}
                    </div>
                  </div>
                  <span className="text-xs text-gray-400">{formatDate(e.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
