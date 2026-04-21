"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { KnowledgeDocument, KnowledgeSpace } from "@/types/api";

export default function KnowledgeHomePage() {
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [keyword, setKeyword] = useState("");

  useEffect(() => {
    api.get<KnowledgeSpace[]>("/knowledge/spaces").then(setSpaces).catch(() => setSpaces([]));
    api
      .get<KnowledgeDocument[]>("/knowledge/documents?status=published")
      .then((list) => setDocs(list || []))
      .catch(() => setDocs([]));
  }, []);

  const shownDocs = docs.filter((d) => {
    const kw = keyword.trim().toLowerCase();
    if (!kw) return true;
    return (
      d.title.toLowerCase().includes(kw) ||
      (d.summary || "").toLowerCase().includes(kw) ||
      d.tags.some((t) => t.toLowerCase().includes(kw))
    );
  });
  const publishedCountBySpace = useMemo(() => {
    const map = new Map<number, number>();
    for (const d of docs) {
      map.set(d.space_id, (map.get(d.space_id) || 0) + 1);
    }
    return map;
  }, [docs]);

  return (
    <div className="mx-auto max-w-6xl space-y-7 p-4 md:p-8">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">知识库</h1>
          <p className="mt-1 text-sm leading-6 text-gray-500">面向长期经营的已发布知识资产，可按空间浏览和提问。</p>
        </div>
        <div className="w-full md:w-80">
          <Input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索标题、摘要或标签"
          />
        </div>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">知识空间</h2>
          <span className="text-xs text-gray-400">{spaces.length} 个空间</span>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {spaces.map((space) => {
            const publishedCount = publishedCountBySpace.get(space.id) || 0;
            const hasPublished = publishedCount > 0;
            return (
              <Card
                key={space.id}
                className={`h-full min-h-[220px] overflow-hidden transition ${hasPublished ? "hover:-translate-y-0.5 hover:border-brand-300" : "opacity-80"}`}
              >
                <CardBody className="flex h-full flex-col">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 text-xl font-semibold tracking-tight text-gray-900 truncate">{space.name}</div>
                    <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-medium ${hasPublished ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>
                      {hasPublished ? `已发布 ${publishedCount} 篇` : "暂无已发布"}
                    </span>
                  </div>
                  <p className="mt-3 min-h-[56px] text-sm leading-6 text-gray-500 line-clamp-2">
                    {space.description || "暂无描述"}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {space.tags.slice(0, 4).map((t) => (
                      <span key={t} className="rounded-full bg-gray-100 px-2 py-1 text-[11px] text-gray-600">
                        {t}
                      </span>
                    ))}
                  </div>
                  <div className="mt-auto pt-3">
                    {hasPublished ? (
                      <Link href={`/dashboard/knowledge/${space.id}`} className="block">
                        <Button size="sm" variant="secondary" className="w-full">进入空间提问</Button>
                      </Link>
                    ) : (
                      <Button size="sm" variant="secondary" className="w-full" disabled>暂无可问答内容</Button>
                    )}
                  </div>
                </CardBody>
              </Card>
            );
          })}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">已发布知识页</h2>
          <span className="text-xs text-gray-400">{shownDocs.length} 篇</span>
        </div>
        {shownDocs.length === 0 ? (
          <Card>
            <CardBody className="text-center text-sm text-gray-500 py-10">
              当前没有匹配的已发布知识页。
            </CardBody>
          </Card>
        ) : (
          <div className="space-y-3">
            {shownDocs.map((doc) => (
              <Card key={doc.id} className="overflow-hidden">
                <CardBody className="flex min-h-[156px] flex-col gap-4 md:flex-row md:items-stretch md:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="text-lg font-semibold tracking-tight text-gray-900">{doc.title}</div>
                    <p className="mt-2 min-h-[56px] text-sm leading-6 text-gray-500 line-clamp-2">{doc.summary || "暂无摘要"}</p>
                    <div className="mt-3 flex min-h-7 flex-wrap gap-1.5">
                      {doc.tags.map((t) => (
                        <span key={t} className="rounded-full bg-gray-100 px-2 py-1 text-[11px] text-gray-600">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex w-full shrink-0 flex-col justify-end border-t border-gray-100 pt-3 md:w-auto md:border-l md:border-t-0 md:pl-4 md:pt-0">
                    <Link href={`/dashboard/knowledge/${doc.space_id}`} className="w-full md:w-auto">
                      <Button variant="secondary" size="sm" className="w-full md:w-auto">进入空间提问</Button>
                    </Link>
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
