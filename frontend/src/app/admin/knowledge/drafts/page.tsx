"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { KnowledgeDocument } from "@/types/api";

function KnowledgeDraftsContent() {
  const params = useSearchParams();
  const presetSpaceId = params.get("space_id");
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [keyword, setKeyword] = useState("");
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const q = new URLSearchParams();
    if (presetSpaceId) q.set("space_id", presetSpaceId);
    api.get<KnowledgeDocument[]>(`/knowledge/documents?${q.toString()}`).then((rows) => {
      setDocs((rows || []).filter((d) => d.status !== "published"));
    }).catch(() => setDocs([]));
  }, [presetSpaceId]);

  const shown = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return docs.filter((d) => {
      if (!kw) return true;
      return (
        d.title.toLowerCase().includes(kw) ||
        (d.summary || "").toLowerCase().includes(kw) ||
        d.tags.some((t) => t.toLowerCase().includes(kw))
      );
    });
  }, [docs, keyword]);

  async function createDraft() {
    if (!presetSpaceId || !title.trim()) return;
    setCreating(true);
    try {
      const detail = await api.post<{ id: number } & Record<string, unknown>>("/knowledge/documents", {
        space_id: Number(presetSpaceId),
        title: title.trim(),
      });
      toast.success("已创建空白草稿");
      setTitle("");
      window.location.href = `/admin/knowledge/drafts/${detail.id}`;
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "创建失败");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-7 p-4 md:p-8">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">知识草稿</h1>
          <p className="mt-1 text-sm leading-6 text-gray-500">展示自动生成和人工编辑中的知识页草稿。</p>
        </div>
        <div className="w-full md:w-80">
          <Input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="搜索草稿" />
        </div>
      </div>

      {presetSpaceId && (
        <Card>
          <CardBody className="flex flex-col gap-3 md:flex-row md:items-center">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="在当前知识空间手工新建一篇知识页"
            />
            <Button onClick={createDraft} disabled={creating || !title.trim()} className="w-full md:w-auto">
              {creating ? "创建中…" : "新建空白草稿"}
            </Button>
          </CardBody>
        </Card>
      )}

      <div className="space-y-3">
        {shown.map((doc) => (
          <Card key={doc.id} className="overflow-hidden">
            <CardBody className="flex min-h-[156px] flex-col gap-4 md:flex-row md:items-stretch md:justify-between">
              <div className="min-w-0 flex-1">
                <div className="text-lg font-semibold tracking-tight text-gray-900">{doc.title}</div>
                <p className="mt-2 min-h-[56px] text-sm leading-6 text-gray-500 line-clamp-2">{doc.summary || "暂无摘要"}</p>
                <div className="mt-3 flex min-h-7 flex-wrap gap-1.5">
                  {doc.tags.map((t) => (
                    <span key={t} className="rounded-full bg-gray-100 px-2 py-1 text-[11px] text-gray-600">{t}</span>
                  ))}
                </div>
              </div>
              <div className="flex w-full shrink-0 flex-col justify-end border-t border-gray-100 pt-3 md:w-auto md:border-l md:border-t-0 md:pl-4 md:pt-0">
                <Link href={`/admin/knowledge/drafts/${doc.id}`} className="w-full md:w-auto">
                  <Button size="sm" className="w-full md:w-auto">进入编辑</Button>
                </Link>
              </div>
            </CardBody>
          </Card>
        ))}
        {shown.length === 0 && (
          <Card>
            <CardBody className="py-10 text-center text-sm text-gray-500">
              暂无草稿。上传资料并解析后，系统会自动生成知识页草稿。
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}

export default function KnowledgeDraftsPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl p-4 text-sm text-gray-500 md:p-8">加载中…</div>
      }
    >
      <KnowledgeDraftsContent />
    </Suspense>
  );
}
