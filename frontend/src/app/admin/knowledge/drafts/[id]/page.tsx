"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { labelKnowledgeStatus } from "@/lib/ui-labels";
import type { KnowledgeDocumentDetail, KnowledgeRevision } from "@/types/api";

export default function KnowledgeDraftDetailPage({ params }: { params: { id: string } }) {
  const docId = Number(params.id);
  const [doc, setDoc] = useState<KnowledgeDocumentDetail | null>(null);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [reviewComment, setReviewComment] = useState("");
  const [hashAnchor, setHashAnchor] = useState("");
  const markdownRef = useRef<HTMLTextAreaElement | null>(null);

  function normalizeAnchor(text: string): string {
    return (text || "")
      .trim()
      .toLowerCase()
      .replace(/[\\/]/g, "-")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "");
  }

  async function load() {
    const detail = await api.get<KnowledgeDocumentDetail>(`/knowledge/documents/${docId}`);
    setDoc(detail);
  }

  useEffect(() => {
    load().catch(() => setDoc(null));
  }, [docId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const updateHash = () => setHashAnchor((window.location.hash || "").replace(/^#/, "").trim());
    updateHash();
    window.addEventListener("hashchange", updateHash);
    return () => window.removeEventListener("hashchange", updateHash);
  }, []);

  const revision = useMemo<KnowledgeRevision | null>(() => doc?.current_revision || null, [doc]);
  const matchedAnchorTitle = useMemo(() => {
    if (!revision || !hashAnchor) return "";
    const fromOutline = (revision.outline || []).find((x) => {
      const title = String(x?.title || "");
      return normalizeAnchor(title) === hashAnchor;
    });
    if (fromOutline) return String(fromOutline.title || "");

    const lines = (revision.markdown_content || "").split("\n");
    for (const raw of lines) {
      const line = raw.trim();
      if (!line.startsWith("#")) continue;
      const title = line.replace(/^#+\s*/, "").trim();
      if (title && normalizeAnchor(title) === hashAnchor) return title;
    }
    return "";
  }, [revision, hashAnchor]);

  useEffect(() => {
    if (!hashAnchor || !revision?.markdown_content || !markdownRef.current) return;
    const text = revision.markdown_content;
    const lines = text.split("\n");
    let cursorPos = -1;
    let offset = 0;
    for (const raw of lines) {
      const line = raw.trim();
      if (line.startsWith("#")) {
        const title = line.replace(/^#+\s*/, "").trim();
        if (title && normalizeAnchor(title) === hashAnchor) {
          cursorPos = offset;
          break;
        }
      }
      offset += raw.length + 1;
    }
    if (cursorPos < 0) return;
    const input = markdownRef.current;
    input.scrollIntoView({ behavior: "smooth", block: "center" });
    input.focus();
    try {
      input.setSelectionRange(cursorPos, cursorPos);
    } catch {
      // noop for unsupported environments
    }
  }, [hashAnchor, revision?.markdown_content]);

  async function saveDraft() {
    if (!revision || !doc) return;
    setSaving(true);
    try {
      await api.patch(`/knowledge/documents/${doc.id}`, {
        title: revision.title,
        summary: revision.summary,
        category: revision.category,
        tags: revision.tags,
        path_slug: doc.path_slug,
        parent_id: doc.parent_id,
        is_redirect: doc.is_redirect,
        redirect_document_id: doc.redirect_document_id,
      });
      await api.patch(`/knowledge/revisions/${revision.id}`, {
        title: revision.title,
        summary: revision.summary,
        category: revision.category,
        tags: revision.tags,
        markdown_content: revision.markdown_content,
        change_note: revision.change_note,
      });
      toast.success("草稿已保存");
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function submit() {
    if (!revision) return;
    setSubmitting(true);
    try {
      await api.post(`/knowledge/revisions/${revision.id}/submit`, {});
      toast.success("已提交审核");
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function publish() {
    if (!revision) return;
    setPublishing(true);
    try {
      await api.post(`/knowledge/revisions/${revision.id}/publish`, {
        change_note: reviewComment || revision.change_note,
      });
      toast.success("已发布并写入知识检索");
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "发布失败");
    } finally {
      setPublishing(false);
    }
  }

  if (!doc || !revision) {
    return <div className="p-8 text-sm text-gray-500">未找到该知识页。</div>;
  }

  return (
    <div className="mx-auto grid max-w-7xl gap-6 p-4 md:p-8 xl:grid-cols-[1fr_360px]">
      <Card>
        <CardBody className="space-y-4">
          {hashAnchor && (
            <div className="rounded-xl border border-brand-100 bg-brand-50 px-3 py-2 text-sm text-brand-900">
              <div className="flex items-center justify-between gap-2">
                <div className="font-medium">已按引用锚点定位</div>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    markdownRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                    markdownRef.current?.focus();
                  }}
                >
                  跳到正文编辑区
                </Button>
              </div>
              <div className="mt-1 text-xs text-brand-700">
                {matchedAnchorTitle
                  ? `当前锚点：${matchedAnchorTitle}`
                  : `当前锚点：${hashAnchor}（正文中未找到完全匹配标题，可手工定位）`}
              </div>
            </div>
          )}
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="text-xs text-gray-400">知识页 #{doc.id}</div>
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">{doc.title}</h1>
            </div>
            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
              <Button variant="secondary" onClick={saveDraft} disabled={saving} className="w-full sm:w-auto">
                {saving ? "保存中…" : "保存草稿"}
              </Button>
              <Button onClick={submit} disabled={submitting} className="w-full sm:w-auto">
                {submitting ? "提交中…" : "提交审核"}
              </Button>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <Input
              value={revision.title}
              onChange={(e) => setDoc((d) => d ? {
                ...d,
                current_revision: d.current_revision ? { ...d.current_revision, title: e.target.value } : null,
              } : d)}
              placeholder="标题"
            />
            <Input
              value={revision.category || ""}
              onChange={(e) => setDoc((d) => d ? {
                ...d,
                current_revision: d.current_revision ? { ...d.current_revision, category: e.target.value } : null,
              } : d)}
              placeholder="分类"
            />
          </div>

          <Input
            value={revision.tags.join(", ")}
            onChange={(e) => setDoc((d) => d ? {
              ...d,
              current_revision: d.current_revision
                ? { ...d.current_revision, tags: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) }
                : null,
            } : d)}
            placeholder="标签（逗号分隔）"
          />

          <textarea
            value={revision.summary || ""}
            onChange={(e) => setDoc((d) => d ? {
              ...d,
              current_revision: d.current_revision ? { ...d.current_revision, summary: e.target.value } : null,
            } : d)}
            rows={3}
            placeholder="摘要"
            className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm outline-none focus:border-brand-500"
          />

          <textarea
            ref={markdownRef}
            value={revision.markdown_content}
            onChange={(e) => setDoc((d) => d ? {
              ...d,
              current_revision: d.current_revision ? { ...d.current_revision, markdown_content: e.target.value } : null,
            } : d)}
            rows={26}
            placeholder="正文（可含标题、列表等格式标记）"
            className="w-full rounded-xl border border-gray-200 px-3 py-2 font-mono text-sm outline-none focus:border-brand-500"
          />
        </CardBody>
      </Card>

      <div className="space-y-6">
        <Card>
          <CardBody className="space-y-3">
            <div className="text-sm font-semibold text-gray-900">Wiki页面设置</div>
            <Input
              value={doc.path_slug || ""}
              onChange={(e) => setDoc((d) => (d ? { ...d, path_slug: e.target.value } : d))}
              placeholder="页面路径（同空间内唯一）"
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                value={doc.parent_id ?? ""}
                onChange={(e) => {
                  const raw = e.target.value.trim();
                  const n = Number(raw);
                  setDoc((d) => (d ? { ...d, parent_id: raw && Number.isFinite(n) ? n : null } : d));
                }}
                placeholder="父页面 ID（可选）"
              />
              <Input
                value={doc.redirect_document_id ?? ""}
                onChange={(e) => {
                  const raw = e.target.value.trim();
                  const n = Number(raw);
                  setDoc((d) => (d ? { ...d, redirect_document_id: raw && Number.isFinite(n) ? n : null } : d));
                }}
                placeholder="重定向到页面 ID（可选）"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={doc.is_redirect}
                onChange={(e) => setDoc((d) => (d ? { ...d, is_redirect: e.target.checked } : d))}
              />
              这是一个重定向页面
            </label>
            <div className="h-px bg-gray-100" />
            <div className="text-sm font-semibold text-gray-900">发布信息</div>
            <div>
              <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
                当前状态：{labelKnowledgeStatus(revision.status)}
              </span>
            </div>
            <textarea
              value={reviewComment}
              onChange={(e) => setReviewComment(e.target.value)}
              rows={3}
              placeholder="发布说明 / 变更说明"
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm outline-none focus:border-brand-500"
            />
            <Button onClick={publish} disabled={publishing} className="w-full">
              {publishing ? "发布中…" : "直接发布"}
            </Button>
            {doc.published_revision && (
              <div className="rounded-2xl bg-gray-50 p-3 text-xs text-gray-500">
                当前线上版本：v{doc.published_revision.version_no}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardBody className="space-y-3">
            <div className="text-sm font-semibold text-gray-900">冲突与溯源</div>
            <div className="space-y-2">
              {doc.conflicts.map((c) => (
                <Link key={c.id} href={`/admin/knowledge/conflicts/${c.id}`} className="block rounded-2xl border border-amber-200 bg-amber-50 p-3">
                  <div className="font-medium text-amber-900">{c.title}</div>
                  <div className="text-xs text-amber-700 mt-1">{c.detail || "待人工处理"}</div>
                </Link>
              ))}
              {doc.conflicts.length === 0 && (
                <div className="rounded-2xl border border-gray-100 p-3 text-sm text-gray-500">当前未发现冲突。</div>
              )}
            </div>
            <div className="text-xs text-gray-400">来源条目：{doc.sources.length}</div>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="space-y-3">
            <div className="text-sm font-semibold text-gray-900">历史版本</div>
            <div className="space-y-2">
              {doc.revisions.map((r) => (
                <div key={r.id} className="rounded-2xl border border-gray-100 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-medium text-sm text-gray-900">v{r.version_no}</div>
                    <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
                      {labelKnowledgeStatus(r.status)}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{r.change_note || "无变更说明"}</div>
                  <div className="mt-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={async () => {
                        try {
                          await api.post(`/knowledge/documents/${doc.id}/rollback?revision_id=${r.id}`, {});
                          toast.success("已创建回滚草稿");
                          await load();
                        } catch (err) {
                          toast.error(err instanceof ApiError ? err.detail : "回滚失败");
                        }
                      }}
                    >
                      回滚为新草稿
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
