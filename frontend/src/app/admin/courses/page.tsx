"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { Course } from "@/types/api";
import { labelCourseStatus } from "@/lib/ui-labels";
import { Plus } from "lucide-react";

export default function AdminCoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState<string>("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", category: "" });
  const [creating, setCreating] = useState(false);

  const load = (kw = "", st = "") => {
    const q = new URLSearchParams();
    if (kw.trim()) q.set("keyword", kw.trim());
    if (st) q.set("status", st);
    const suffix = q.toString() ? `?${q.toString()}` : "";
    return api.get<Course[]>(`/courses${suffix}`).then(setCourses);
  };

  useEffect(() => {
    const t = setTimeout(() => {
      load(keyword, status);
    }, 250);
    return () => clearTimeout(t);
  }, [keyword, status]);

  async function create() {
    if (!form.title.trim()) return;
    setCreating(true);
    try {
      await api.post("/courses", {
        title: form.title,
        description: form.description || null,
        category: form.category || null,
        tags: [],
      });
      setForm({ title: "", description: "", category: "" });
      setShowForm(false);
      toast.success("创建成功");
      load();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "创建失败";
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">课程管理</h1>
          <p className="text-sm text-gray-500">上传课件、生成题库、编辑课程</p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>
          <Plus className="h-4 w-4" /> 新建课程
        </Button>
      </div>

      <div className="mb-4 grid gap-2 md:grid-cols-[1fr_180px_auto]">
        <Input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索课程名称、简介或分类"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="h-12 px-3 rounded-lg border border-gray-200 bg-white text-base"
        >
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="processing">处理中</option>
          <option value="ready">可学习</option>
        </select>
        <Button
          variant="secondary"
          onClick={() => {
            setKeyword("");
            setStatus("");
          }}
        >
          清空筛选
        </Button>
      </div>

      {showForm && (
        <Card className="mb-6">
          <CardBody className="space-y-3">
            <Input
              placeholder="课程名称"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <Input
              placeholder="分类（如：产品、销售、合规）"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            />
            <Textarea
              placeholder="课程简介"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setShowForm(false)}>取消</Button>
              <Button onClick={create} disabled={creating || !form.title.trim()}>
                {creating ? "创建中..." : "创建"}
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {courses.map((c) => (
          <Link href={`/admin/courses/${c.id}`} key={c.id}>
            <Card className="hover:border-brand-500 transition cursor-pointer h-full">
              <CardBody>
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-gray-900 line-clamp-1">{c.title}</h3>
                  <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">{labelCourseStatus(c.status)}</span>
                </div>
                <p className="text-sm text-gray-500 line-clamp-2 min-h-[40px]">{c.description || "—"}</p>
                <div className="mt-2 text-xs text-gray-400">分类：{c.category || "未分类"}</div>
              </CardBody>
            </Card>
          </Link>
        ))}
      </div>
      {courses.length === 0 && (
        <Card className="mt-4">
          <CardBody className="text-gray-500 text-center py-8">
            未找到匹配课程
          </CardBody>
        </Card>
      )}
    </div>
  );
}
