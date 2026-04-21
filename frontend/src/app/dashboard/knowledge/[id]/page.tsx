"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { AskResponse, KnowledgeDocument, KnowledgeSpace } from "@/types/api";

type Msg = { role: "user" | "assistant"; content: string; sources?: AskResponse["sources"] };

export default function KnowledgeSpacePage({ params }: { params: { id: string } }) {
  const spaceId = Number(params.id);
  const [space, setSpace] = useState<KnowledgeSpace | null>(null);
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.get<KnowledgeSpace[]>("/knowledge/spaces").then((list) => {
      const item = (list || []).find((x) => x.id === spaceId) || null;
      setSpace(item);
    }).catch(() => setSpace(null));
    api
      .get<KnowledgeDocument[]>(`/knowledge/documents?space_id=${spaceId}&status=published`)
      .then((list) => setDocs(list || []))
      .catch(() => setDocs([]));
  }, [spaceId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, asking]);

  async function ask() {
    const q = question.trim();
    if (!q || asking) return;
    setMsgs((m) => [...m, { role: "user", content: q }]);
    setQuestion("");
    setAsking(true);
    try {
      const res = await api.post<AskResponse>(`/knowledge/spaces/${spaceId}/ask`, {
        question: q,
        response_style: "standard",
        rewrite: true,
      });
      setMsgs((m) => [...m, { role: "assistant", content: res.answer, sources: res.sources }]);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : "提问失败";
      setMsgs((m) => [...m, { role: "assistant", content: `提问失败：${detail}` }]);
    } finally {
      setAsking(false);
    }
  }

  const title = useMemo(() => space?.name || "知识空间", [space]);
  const docIdByPath = useMemo(() => {
    const map = new Map<string, number>();
    for (const d of docs) {
      if (d.path_slug) map.set(d.path_slug, d.id);
    }
    return map;
  }, [docs]);

  return (
    <div className="mx-auto grid max-w-6xl gap-6 p-4 md:p-8 lg:grid-cols-[320px_1fr]">
      <Card className="h-fit">
        <CardBody>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-gray-500">{space?.description || "基于已发布知识资产进行检索问答。"}</p>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {(space?.tags || []).map((t) => (
              <span key={t} className="rounded-full bg-gray-100 px-2 py-1 text-[11px] text-gray-600">{t}</span>
            ))}
          </div>
          <div className="mt-6">
            <div className="text-sm font-semibold text-gray-900 mb-2">已发布知识页</div>
            <div className="space-y-2 max-h-[420px] overflow-y-auto">
              {docs.map((doc) => (
                <div key={doc.id} className="rounded-2xl border border-gray-100 bg-gray-50/40 px-3.5 py-3">
                  <div className="font-medium text-sm text-gray-900">{doc.title}</div>
                  <div className="mt-1 min-h-[40px] text-xs leading-5 text-gray-500 line-clamp-2">
                    {doc.summary || "暂无摘要"}
                  </div>
                </div>
              ))}
              {docs.length === 0 && (
                <div className="text-sm text-gray-400">该空间还没有已发布知识页。</div>
              )}
            </div>
          </div>
        </CardBody>
      </Card>

      <Card className="min-h-[70vh]">
        <CardBody className="flex h-full flex-col">
          <div className="flex-1 space-y-3 overflow-y-auto">
            {msgs.length === 0 && (
              <div className="h-full min-h-[280px] flex items-center justify-center text-center text-sm text-gray-400">
                试着问一个知识问题，例如“请总结这个知识库里关于禁忌事项的核心要点”
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                <div className={m.role === "user"
                  ? "max-w-[88%] rounded-2xl rounded-br-md bg-gray-900 px-4 py-3 text-sm leading-6 text-white"
                  : "max-w-[88%] rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-3 text-sm leading-6 text-gray-800"}>
                  {m.role === "assistant" ? (
                    <div className="prose prose-sm max-w-none prose-gray">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                    </div>
                  ) : (
                    m.content
                  )}
                  {m.sources && m.sources.length > 0 && (
                    <details className="mt-2 border-t border-gray-100 pt-2 text-xs text-gray-500">
                      <summary className="cursor-pointer">查看引用来源（{m.sources.length}）</summary>
                      <ul className="mt-2 space-y-1.5">
                        {m.sources.map((s) => {
                          const wikiDocId = s.wiki_path ? docIdByPath.get(s.wiki_path) : undefined;
                          return (
                          <li key={s.index} className="rounded-lg bg-gray-50 px-2 py-1.5">
                            <div className="font-medium text-gray-700">[S{s.index}] {s.chapter || "未分章"}</div>
                            {(s.wiki_path || s.wiki_section) && (
                              <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
                                <span>
                                  来自：{s.wiki_path || "未命名页面"}{s.wiki_section ? ` / ${s.wiki_section}` : ""}
                                </span>
                                {s.wiki_path && wikiDocId && (
                                  <Link
                                    href={`/admin/knowledge/drafts/${wikiDocId}${s.wiki_section_anchor ? `#${s.wiki_section_anchor}` : ""}`}
                                    className="rounded-full bg-white px-2 py-0.5 text-[10px] font-medium text-brand-700 hover:bg-brand-50"
                                  >
                                    打开Wiki页面
                                  </Link>
                                )}
                              </div>
                            )}
                            <div className="text-gray-500">{s.snippet}</div>
                          </li>
                        );})}
                      </ul>
                    </details>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
          <div className="mt-4 flex flex-col gap-2 border-t border-gray-100 pt-4 sm:flex-row">
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
              placeholder="输入你的问题…"
              disabled={asking}
              className="sm:flex-1"
            />
            <Button
              onClick={ask}
              disabled={asking || !question.trim()}
              className="w-full sm:w-auto sm:min-w-24"
            >
              {asking ? "思考中…" : "发送"}
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
