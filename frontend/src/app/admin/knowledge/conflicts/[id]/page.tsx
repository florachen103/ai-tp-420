"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { labelKnowledgeConflictStatus, labelKnowledgeConflictType } from "@/lib/ui-labels";
import type { KnowledgeConflict } from "@/types/api";

const ACTIONS = [
  { id: "keep_existing", label: "保留线上版本" },
  { id: "use_incoming", label: "采用新草稿" },
  { id: "merged", label: "人工合并" },
  { id: "ignored", label: "忽略提醒" },
] as const;

export default function ConflictDetailPage({ params }: { params: { id: string } }) {
  const conflictId = Number(params.id);
  const [data, setData] = useState<KnowledgeConflict | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get<KnowledgeConflict>(`/knowledge/conflicts/${conflictId}`).then(setData);

  useEffect(() => {
    load().catch(() => setData(null));
  }, [conflictId]);

  async function resolve(resolution_kind: string) {
    setBusy(true);
    try {
      await api.post(`/knowledge/conflicts/${conflictId}/resolve`, {
        resolution_kind,
        comment,
      });
      toast.success("冲突状态已更新");
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "处理失败");
    } finally {
      setBusy(false);
    }
  }

  if (!data) {
    return <div className="p-8 text-sm text-gray-500">未找到该冲突。</div>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-7 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">{data.title}</h1>
        <p className="mt-1 text-xs text-gray-400">类型：{labelKnowledgeConflictType(data.conflict_type)}</p>
        <p className="mt-2 text-sm leading-6 text-gray-500">{data.detail || "请人工确认两侧内容是否冲突。"}</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardBody>
            <div className="text-sm font-semibold text-gray-900 mb-3">线上版本片段</div>
            <pre className="rounded-2xl bg-gray-50 p-4 text-xs leading-6 whitespace-pre-wrap text-gray-600">
              {data.existing_excerpt || "暂无"}
            </pre>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <div className="text-sm font-semibold text-gray-900 mb-3">新草稿片段</div>
            <pre className="rounded-2xl bg-gray-50 p-4 text-xs leading-6 whitespace-pre-wrap text-gray-600">
              {data.incoming_excerpt || "暂无"}
            </pre>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardBody className="space-y-3">
          <div className="text-sm font-semibold text-gray-900">处理动作</div>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            placeholder="填写处理说明"
            className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm outline-none focus:border-brand-500"
          />
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {ACTIONS.map((item) => (
              <Button
                key={item.id}
                variant={item.id === "use_incoming" ? "primary" : "secondary"}
                onClick={() => resolve(item.id)}
                disabled={busy}
                className="w-full sm:w-auto"
              >
                {item.label}
              </Button>
            ))}
          </div>
          <div>
            <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
              当前状态：{labelKnowledgeConflictStatus(data.status)}
            </span>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
