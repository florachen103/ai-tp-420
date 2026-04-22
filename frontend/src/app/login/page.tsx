"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardBody } from "@/components/ui/card";
import { useAuth } from "@/lib/auth-store";
import { ApiError } from "@/lib/api";

const LOGIN_BRAND_ICON = "https://i.hd-r.cn/02bc63f0-0cf3-48ab-a224-ad5f4f0aec0e.png";

export default function LoginPage() {
  const router = useRouter();
  const { login, register, sendRegisterCode } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [form, setForm] = useState({ email: "", password: "", name: "", department: "", verificationCode: "" });
  const [loading, setLoading] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setInterval(() => {
      setCooldown((v) => (v > 0 ? v - 1 : 0));
    }, 1000);
    return () => clearInterval(t);
  }, [cooldown]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "login") {
        await login(form.email, form.password);
        toast.success("登录成功");
      } else {
        await register(
          form.email,
          form.password,
          form.name,
          form.verificationCode,
          form.department || undefined
        );
        toast.success("注册成功");
      }
      router.push("/dashboard");
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "请求失败";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }

  async function onSendCode() {
    if (!form.email.trim()) {
      toast.error("请先填写邮箱");
      return;
    }
    setSendingCode(true);
    try {
      await sendRegisterCode(form.email.trim());
      toast.success("验证码已发送，请查看邮箱");
      setCooldown(60);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "发送失败";
      toast.error(msg);
    } finally {
      setSendingCode(false);
    }
  }

  return (
    <div className="min-h-screen grid md:grid-cols-2 bg-gray-50">
      <div className="hidden md:flex flex-col justify-between p-10 bg-gradient-to-br from-[#E6002D] to-[#F68B1F] text-white">
        <div>
          <div className="flex items-center gap-2">
            <Image
              src={LOGIN_BRAND_ICON}
              alt="智能培训平台"
              width={40}
              height={40}
              className="h-10 w-10 rounded-xl object-contain bg-white/15 p-1 backdrop-blur"
              priority
            />
            <span className="text-xl font-semibold">智能培训平台</span>
          </div>
        </div>
        <div>
          <h1 className="text-3xl font-bold leading-snug">
            把你的私有资料
            <br />
            变成员工的专属导师
          </h1>
          <p className="mt-4 text-white/80 text-sm leading-relaxed">
            上传文稿、PDF、演示稿、表格等资料，一键生成智能问答、模拟题、在线考试。
            <br />
            基于知识库精准检索，结合顾客画像生成个性化培训话术。
          </p>
        </div>
        <div className="text-xs text-white/60">© 2026 企业内训系统</div>
      </div>

      <div className="flex items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardBody>
            <div className="mb-6">
              <h2 className="text-2xl font-semibold text-gray-900">
                {mode === "login" ? "登录" : "注册"}
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                {mode === "login" ? "使用邮箱登录" : "首个注册者将成为管理员"}
              </p>
            </div>

            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <label className="text-sm text-gray-700 mb-1 block">邮箱</label>
                <Input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required
                  placeholder="请输入常用邮箱"
                />
              </div>
              {mode === "register" && (
                <>
                  <div>
                    <label className="text-sm text-gray-700 mb-1 block">姓名</label>
                    <Input
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      required
                      placeholder="请输入您的姓名"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-gray-700 mb-1 block">部门</label>
                    <Input
                      value={form.department}
                      onChange={(e) => setForm({ ...form, department: e.target.value })}
                      placeholder="如：销售部（选填）"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-gray-700 mb-1 block">邮箱验证码</label>
                    <div className="flex gap-2">
                      <Input
                        value={form.verificationCode}
                        onChange={(e) => setForm({ ...form, verificationCode: e.target.value })}
                        placeholder="请输入6位验证码"
                      />
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={sendingCode || cooldown > 0}
                        onClick={onSendCode}
                      >
                        {sendingCode ? "发送中..." : cooldown > 0 ? `${cooldown}s` : "发送验证码"}
                      </Button>
                    </div>
                  </div>
                </>
              )}
              <div>
                <label className="text-sm text-gray-700 mb-1 block">密码</label>
                <Input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  required
                  minLength={6}
                  placeholder="至少 6 位"
                />
              </div>

              <Button type="submit" size="lg" className="w-full" disabled={loading}>
                {loading ? "处理中..." : mode === "login" ? "登录" : "注册并登录"}
              </Button>
            </form>

            <div className="mt-4 text-center text-sm text-gray-500">
              {mode === "login" ? "还没有账号？" : "已有账号？"}
              <button
                className="text-brand-600 ml-1 hover:underline"
                onClick={() => setMode(mode === "login" ? "register" : "login")}
              >
                {mode === "login" ? "注册新账号" : "返回登录"}
              </button>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
