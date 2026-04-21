"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { KnowledgeSpace } from "@/types/api";

export default function KnowledgeSpacesPage() {
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    slug: "",
    category: "",
    tags: "",
    description: "",
  });

  const load = () => api.get<KnowledgeSpace[]>("/knowledge/spaces").then(setSpaces);

  useEffect(() => {
    load().catch(() => setSpaces([]));
  }, []);

  async function create() {
    if (!form.name.trim() || !form.slug.trim()) return;
    setCreating(true);
    try {
      await api.post("/knowledge/spaces", {
        name: form.name.trim(),
        slug: form.slug.trim(),
        category: form.category.trim() || null,
        description: form.description.trim() || null,
        tags: form.tags.split(",").map((x) => x.trim()).filter(Boolean),
      });
      toast.success("知识空间已创建");
      setShowForm(false);
      setForm({ name: "", slug: "", category: "", tags: "", description: "" });
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "创建失败");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-7 p-4 md:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">知识空间</h1>
          <p className="mt-1 text-sm leading-6 text-gray-500">管理长期经营的知识空间，是草稿、审核、发布的最上层容器。</p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)} className="w-full sm:w-auto">
          {showForm ? "收起" : "新建空间"}
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardBody className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-1.5">
                <Input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="空间名称"
                />
              </div>
              <div className="space-y-1.5">
                <Input
                  value={form.slug}
                  onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
                  placeholder="访问名称（建议用拼音或英文）"
                />
                <p className="px-1 text-xs leading-5 text-gray-400">
                  这是这个知识空间的访问简称。建议填写拼音或英文短词，例如 `huang-qi-jing`。
                </p>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Input
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                placeholder="分类"
              />
              <Input
                value={form.tags}
                onChange={(e) => setForm((f) => ({ ...f, tags: e.target.value }))}
                placeholder="标签（逗号分隔）"
              />
            </div>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="空间说明"
              rows={3}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm outline-none focus:border-brand-500"
            />
            <div className="flex flex-col justify-end gap-2 sm:flex-row">
              <Button variant="secondary" onClick={() => setShowForm(false)} className="w-full sm:w-auto">取消</Button>
              <Button onClick={create} disabled={creating || !form.name.trim() || !form.slug.trim()} className="w-full sm:w-auto">
                {creating ? "创建中…" : "创建"}
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {spaces.map((space) => (
          <Card key={space.id} className="h-full min-h-[220px] overflow-hidden">
            <CardBody className="flex h-full flex-col">
              <div>
                <div className="text-xl font-semibold tracking-tight text-gray-900">{space.name}</div>
              </div>
              <p className="mt-3 min-h-[56px] text-sm leading-6 text-gray-500 line-clamp-2">
                {space.description || "暂无描述"}
              </p>
              <div className="mt-3 flex min-h-7 flex-wrap gap-1.5">
                {space.tags.map((t) => (
                  <span key={t} className="rounded-full bg-brand-50 px-2 py-1 text-[11px] font-medium text-brand-700">
                    {t}
                  </span>
                ))}
              </div>
              <div className="mt-auto flex flex-col gap-2 border-t border-gray-100 pt-3 sm:flex-row">
                <Link href={`/admin/knowledge/wiki?space_id=${space.id}`} className="flex-1">
                  <Button variant="secondary" size="sm" className="w-full">Wiki目录</Button>
                </Link>
                <Link href={`/admin/knowledge/drafts?space_id=${space.id}`} className="flex-1">
                  <Button variant="secondary" size="sm" className="w-full">查看草稿</Button>
                </Link>
                <Link href={`/dashboard/knowledge/${space.id}`} className="flex-1">
                  <Button size="sm" className="w-full">前台问答</Button>
                </Link>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
