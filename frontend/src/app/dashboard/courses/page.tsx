"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardBody } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Course } from "@/types/api";
import { BookOpen, FileText } from "lucide-react";

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft:      { label: "草稿",    color: "bg-gray-100 text-gray-600" },
  processing: { label: "解析中",  color: "bg-amber-100 text-amber-700" },
  ready:      { label: "可学习",  color: "bg-emerald-100 text-emerald-700" },
  archived:   { label: "已归档",  color: "bg-gray-100 text-gray-500" },
};

export default function CoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<Course[]>("/courses").then(setCourses).finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">课程中心</h1>
          <p className="text-sm text-gray-500">选择一门课程开始学习</p>
        </div>
      </div>

      {loading ? (
        <div className="text-gray-500">加载中...</div>
      ) : courses.length === 0 ? (
        <Card>
          <CardBody className="text-center py-12 text-gray-500">
            <BookOpen className="h-10 w-10 mx-auto mb-3 text-gray-300" />
            暂无课程，请联系管理员上传课件
          </CardBody>
        </Card>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {courses.map((c) => {
            const s = STATUS_MAP[c.status] || STATUS_MAP.draft;
            return (
              <Link href={`/dashboard/courses/${c.id}`} key={c.id}>
                <Card className="hover:border-brand-500 hover:shadow-md transition cursor-pointer h-full">
                  <CardBody>
                    <div className="flex items-start justify-between mb-3">
                      <div className="h-10 w-10 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center">
                        <FileText className="h-5 w-5" />
                      </div>
                      <span className={`px-2 py-0.5 rounded text-xs ${s.color}`}>{s.label}</span>
                    </div>
                    <h3 className="font-semibold text-gray-900 line-clamp-1">{c.title}</h3>
                    <p className="mt-1 text-sm text-gray-500 line-clamp-2 min-h-[40px]">
                      {c.description || "暂无简介"}
                    </p>
                    {c.tags.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1">
                        {c.tags.slice(0, 3).map((t) => (
                          <span key={t} className="text-xs px-2 py-0.5 bg-gray-50 text-gray-600 rounded">{t}</span>
                        ))}
                      </div>
                    )}
                  </CardBody>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
