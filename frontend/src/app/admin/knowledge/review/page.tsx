"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { KnowledgeRevision } from "@/types/api";

export default function KnowledgeReviewPage() {
  const [rows, setRows] = useState<KnowledgeRevision[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = () => api.get<KnowledgeRevision[]>("/knowledge/review/queue").then(setRows);

  useEffect(() => {
    load().catch(() => setRows([]));
  }, []);

  async function review(id: number, action: "approve" | "reject") {
    setBusyId(id);
    try {
      await api.post(`/knowledge/review/${id}/${action}`, {
        comment: action === "approve" ? "审核通过，待发布" : "请按意见修改后重新提交",
      });
      toast.success(action === "approve" ? "已审核通过" : "已驳回");
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "操作失败");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-7 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">审核工作台</h1>
        <p className="mt-1 text-sm leading-6 text-gray-500">对已提交的知识草稿做事实核验、通过或驳回。</p>
      </div>

      <div className="space-y-3">
        {rows.map((row) => (
          <Card key={row.id} className="overflow-hidden">
            <CardBody className="flex min-h-[220px] flex-col gap-4">
              <div className="flex flex-col gap-4 md:flex-row md:items-stretch md:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="text-lg font-semibold tracking-tight text-gray-900">{row.title}</div>
                  <div className="mt-1 text-xs text-gray-400">文档 #{row.document_id} · v{row.version_no}</div>
                  <p className="mt-2 min-h-[56px] text-sm leading-6 text-gray-500 line-clamp-2">{row.summary || "暂无摘要"}</p>
                  <pre className="mt-3 max-h-40 overflow-auto rounded-2xl bg-gray-50/90 p-4 text-xs leading-6 whitespace-pre-wrap text-gray-600">
                    {row.markdown_content.slice(0, 1200)}
                  </pre>
                </div>
                <div className="flex w-full flex-col justify-end gap-2 border-t border-gray-100 pt-3 sm:w-auto sm:flex-row md:border-l md:border-t-0 md:pl-4 md:pt-0">
                  <Link href={`/admin/knowledge/drafts/${row.document_id}`} className="w-full sm:w-auto">
                    <Button variant="secondary" size="sm" className="w-full sm:w-auto">打开详情</Button>
                  </Link>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={busyId === row.id}
                    onClick={() => review(row.id, "reject")}
                    className="w-full sm:w-auto"
                  >
                    驳回
                  </Button>
                  <Button
                    size="sm"
                    disabled={busyId === row.id}
                    onClick={() => review(row.id, "approve")}
                    className="w-full sm:w-auto"
                  >
                    通过
                  </Button>
                </div>
              </div>
            </CardBody>
          </Card>
        ))}
        {rows.length === 0 && (
          <Card>
            <CardBody className="py-10 text-center text-sm text-gray-500">当前没有待审核草稿。</CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}
