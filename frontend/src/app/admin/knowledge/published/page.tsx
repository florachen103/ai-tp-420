"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { KnowledgeDocument } from "@/types/api";

export default function KnowledgePublishedPage() {
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);

  useEffect(() => {
    api.get<KnowledgeDocument[]>("/knowledge/documents?status=published").then(setDocs).catch(() => setDocs([]));
  }, []);

  return (
    <div className="mx-auto max-w-6xl space-y-7 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">已发布知识</h1>
        <p className="mt-1 text-sm leading-6 text-gray-500">线上生效中的知识页，课程问答和知识问答优先消费这里的内容。</p>
      </div>

      <div className="space-y-3">
        {docs.map((doc) => (
          <Card key={doc.id} className="overflow-hidden">
            <CardBody className="flex min-h-[156px] flex-col gap-4 md:flex-row md:items-stretch md:justify-between">
              <div className="min-w-0 flex-1">
                <div className="text-lg font-semibold tracking-tight text-gray-900">{doc.title}</div>
                <p className="mt-2 min-h-[56px] text-sm leading-6 text-gray-500 line-clamp-2">{doc.summary || "暂无摘要"}</p>
              </div>
              <div className="flex w-full flex-col justify-end gap-2 border-t border-gray-100 pt-3 sm:w-auto sm:flex-row md:border-l md:border-t-0 md:pl-4 md:pt-0">
                <Link href={`/dashboard/knowledge/${doc.space_id}`} className="w-full sm:w-auto">
                  <Button size="sm" variant="secondary" className="w-full sm:w-auto">
                    前台查看
                  </Button>
                </Link>
                <Link href={`/admin/knowledge/drafts/${doc.id}`} className="w-full sm:w-auto">
                  <Button size="sm" className="w-full sm:w-auto">
                    查看版本
                  </Button>
                </Link>
              </div>
            </CardBody>
          </Card>
        ))}
        {docs.length === 0 && (
          <Card>
            <CardBody className="py-10 text-center text-sm text-gray-500">当前还没有发布中的知识页。</CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}
