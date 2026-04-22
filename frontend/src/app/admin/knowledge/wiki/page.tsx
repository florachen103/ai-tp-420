"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { KnowledgeSpace, KnowledgeTreeNode } from "@/types/api";

type TreeNode = KnowledgeTreeNode & { children: TreeNode[] };

function buildTree(nodes: KnowledgeTreeNode[]): TreeNode[] {
  const byId = new Map<number, TreeNode>();
  for (const n of nodes) byId.set(n.id, { ...n, children: [] });
  const roots: TreeNode[] = [];
  for (const node of byId.values()) {
    if (node.parent_id && byId.has(node.parent_id)) {
      byId.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  const sortFn = (a: TreeNode, b: TreeNode) => a.path_slug.localeCompare(b.path_slug, "zh-CN");
  const walk = (list: TreeNode[]) => {
    list.sort(sortFn);
    list.forEach((n) => walk(n.children));
  };
  walk(roots);
  return roots;
}

function TreeList({
  nodes,
  pathById,
  depth = 0,
}: {
  nodes: TreeNode[];
  pathById: Map<number, string>;
  depth?: number;
}) {
  return (
    <ul className="space-y-2">
      {nodes.map((node) => (
        <li key={node.id}>
          <div
            className="flex flex-col gap-2 rounded-xl border border-gray-100 bg-white px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between"
            style={{ marginLeft: depth * 16 }}
          >
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-gray-900">
                {node.title}
                {node.is_redirect ? <span className="ml-2 text-xs text-amber-600">重定向</span> : null}
              </div>
              <div className="mt-1 text-xs text-gray-500">路径：{pathById.get(node.id) || `目录 / ${node.title}`}</div>
            </div>
            <Link href={`/admin/knowledge/drafts/${node.id}`} className="w-full sm:w-auto">
              <Button size="sm" variant="secondary" className="w-full sm:w-auto">
                打开页面
              </Button>
            </Link>
          </div>
          {node.children.length > 0 ? (
            <div className="mt-2">
              <TreeList nodes={node.children} pathById={pathById} depth={depth + 1} />
            </div>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function KnowledgeWikiTreeContent() {
  const params = useSearchParams();
  const preset = params.get("space_id");
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [spaceId, setSpaceId] = useState<number | null>(null);
  const [rows, setRows] = useState<KnowledgeTreeNode[]>([]);

  useEffect(() => {
    api.get<KnowledgeSpace[]>("/knowledge/spaces").then((list) => {
      const all = list || [];
      setSpaces(all);
      setSpaceId((prev) => prev ?? (preset ? Number(preset) : all[0]?.id ?? null));
    }).catch(() => {
      setSpaces([]);
      setSpaceId(null);
    });
  }, [preset]);

  useEffect(() => {
    if (!spaceId) {
      setRows([]);
      return;
    }
    api.get<KnowledgeTreeNode[]>(`/knowledge/spaces/${spaceId}/tree`)
      .then((list) => setRows(list || []))
      .catch(() => setRows([]));
  }, [spaceId]);

  const tree = useMemo(() => buildTree(rows), [rows]);
  const pathById = useMemo(() => {
    const titleById = new Map<number, string>();
    const parentById = new Map<number, number | null>();
    for (const r of rows) {
      titleById.set(r.id, r.title);
      parentById.set(r.id, r.parent_id);
    }
    const out = new Map<number, string>();
    for (const r of rows) {
      const chain: string[] = [r.title];
      let parentId = r.parent_id;
      let guard = 0;
      while (parentId && guard < 30) {
        const parentTitle = titleById.get(parentId);
        if (!parentTitle) break;
        chain.unshift(parentTitle);
        parentId = parentById.get(parentId) ?? null;
        guard += 1;
      }
      out.set(r.id, `目录 / ${chain.join(" / ")}`);
    }
    return out;
  }, [rows]);

  return (
    <div className="mx-auto max-w-6xl space-y-7 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Wiki目录</h1>
        <p className="mt-1 text-sm leading-6 text-gray-500">按页面层级管理知识目录，支持父子页面与重定向页面。</p>
      </div>

      <Card>
        <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <select
            value={spaceId ?? ""}
            onChange={(e) => setSpaceId(Number(e.target.value) || null)}
            className="h-11 w-full rounded-xl border border-gray-200 bg-white px-3 text-sm text-gray-700 sm:max-w-xs"
          >
            {spaces.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <Link href={spaceId ? `/admin/knowledge/drafts?space_id=${spaceId}` : "/admin/knowledge/drafts"} className="w-full sm:w-auto">
            <Button className="w-full sm:w-auto">去草稿列表</Button>
          </Link>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          {tree.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500">当前空间还没有页面目录。</div>
          ) : (
            <TreeList nodes={tree} pathById={pathById} />
          )}
        </CardBody>
      </Card>
    </div>
  );
}

export default function KnowledgeWikiTreePage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl p-4 text-sm text-gray-500 md:p-8">加载中…</div>
      }
    >
      <KnowledgeWikiTreeContent />
    </Suspense>
  );
}
