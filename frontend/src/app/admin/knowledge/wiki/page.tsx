import { Suspense } from "react";
import KnowledgeWikiClient from "./wiki-client";

export default function KnowledgeWikiTreePage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl p-4 text-sm text-gray-500 md:p-8">加载中…</div>
      }
    >
      <KnowledgeWikiClient />
    </Suspense>
  );
}
