# AI 培训平台

基于 RAG 的企业级在线培训系统。把你的私有课件（Word / PDF / PPT / Excel）解析成知识库，为员工提供智能问答、AI 生成模拟题、在线考试、AI 判分和学习数据看板。支持手机端与 PC 端（响应式），可用于生产开发。

---

## 功能（Phase 0 MVP 已完成）

| 模块 | 说明 |
|---|---|
| 用户与鉴权 | 邮箱注册/登录，JWT，首个用户自动成为管理员；支持 admin / manager / learner 三级角色 |
| 课件管理 | 管理员上传 Word / PDF / PPT / Excel / Markdown → 对象存储 → 异步解析 → 向量化入库 |
| RAG 问答 | 学员在课程页向 AI 提问，基于该课程知识库检索 Top-K 相关切片 + LLM 生成答案，附参考来源 |
| 顾客画像话术 | 提问时可附带「顾客画像」，AI 会据此调整话术的专业度与场景 |
| AI 出题 | 一键基于课程内容生成指定数量/类型/难度的模拟题（单选/多选/判断/填空/简答） |
| 在线考试 | 按规则自动抽题、打乱顺序、计时、切屏监测；学员作答流畅 |
| 自动判分 | 客观题精确匹配；简答题由 LLM 基于参考答案判分并给评语 |
| 学习看板 | 个人学习时长、考试通过率、平均分、薄弱知识点分析 |
| 移动端 | 一套代码响应式布局，PC 侧边栏 + 手机底部导航 |

---

## 技术栈

- **前端**：Next.js 14 (App Router) + TypeScript + TailwindCSS + Zustand + sonner
- **后端**：FastAPI + SQLAlchemy 2.0 + Alembic + Celery
- **数据库**：PostgreSQL 16 + pgvector（HNSW 索引）
- **缓存/队列**：Redis
- **对象存储**：MinIO（生产可平滑切换到阿里云 OSS / 腾讯云 COS / AWS S3）
- **AI 提供商抽象层**：一个接口，支持 DeepSeek / OpenAI / 通义千问 / 任意 OpenAI 兼容端点
- **文件解析**：python-docx / pdfplumber / python-pptx / openpyxl / pandas（PDF 支持 OCR 兜底）

---

## 快速启动（Docker Compose，推荐）

前置条件：Docker Desktop 或 Docker Engine + Docker Compose v2。

```bash
# 1. 拷贝环境变量并填入 AI API Key
cp .env.example .env
# 用你熟悉的编辑器打开 .env，至少填好：
#   DEEPSEEK_API_KEY=sk-xxx   （从 https://platform.deepseek.com 获取）
#   DASHSCOPE_API_KEY=sk-xxx  （从 https://dashscope.aliyun.com 获取，用于 embedding）

# 2. 一键启动（初次会拉镜像 + 构建，约 3-5 分钟）
make up          # 或 docker compose up -d

# 3. 打开浏览器
#    前端：        http://localhost:3000
#    后端 API 文档：http://localhost:8000/docs
#    MinIO 控制台：http://localhost:9001  (minioadmin/minioadmin)
```

**首次使用流程**：

1. 打开 `http://localhost:3000/login` → 注册账号（第一个注册的自动成为管理员）
2. 进入 **管理后台 → 课程管理 → 新建课程**
3. 进入课程详情 → **上传课件**（.docx / .pdf / .pptx / .xlsx 等）
4. 等待 30–60 秒（查看底部 "parsed · N 切片" 字样代表就绪）
5. 点 **AI 生成题目** → 生成 10 道模拟题
6. 创建一场 **考试**（自动按规则从题库抽题）
7. 切换到 **学习概览** 进入学员视角 → 课程页向 AI 提问 / 去考试页作答
8. 回看 **学习概览** 查看数据看板

---

## 本地开发（不走 Docker）

### 后端

```bash
# 启动基础依赖
docker compose up -d postgres redis minio

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export $(cat ../.env | grep -v '^#' | xargs)
export POSTGRES_HOST=localhost REDIS_HOST=localhost S3_ENDPOINT=http://localhost:9000

alembic upgrade head
uvicorn app.main:app --reload --port 8000
# 另开一个终端跑 Worker
celery -A app.workers.celery_app worker --loglevel=info
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

---

## 前端部署（Vercel + 后端在 Render 等）

仓库根目录已提供 `render.yaml`，可直接作为 Render Blueprint 导入后端、Worker、Postgres 和 Key Value（Redis 兼容）。  
注意：对象存储未在 Blueprint 中托管，仍需你自己提供一个 S3 兼容服务（如 AWS S3、Cloudflare R2、阿里云 OSS、腾讯云 COS）。

若登录仍请求 **`http://localhost:8000`**，说明线上 bundle 里曾内联过默认地址；请改用下面 **方式 A** 或修正 **方式 B** 后 **Redeploy**。

### 方式 A（推荐）：`BACKEND_ORIGIN` + 服务端 Route 转发

1. Vercel → **Settings** → **Environment Variables** → 新增 **`BACKEND_ORIGIN`**，值为 **仅后端根地址**，**不要**带 `/api/v1`，例如：  
   `https://你的服务.onrender.com`
2. 保存后 **Deployments → Redeploy**（让 Serverless 读到变量）。
3. 浏览器请求 **`https://你的项目.vercel.app/api/v1/...`**（同源），由 **`frontend/src/app/api/v1/[...path]/route.ts`** 在运行时 `fetch` 转发到 Render（比 `next.config` 的 external rewrite 更稳，尤其 POST）。**一般不必**再为浏览器配置直连后端的 CORS。

若你曾配置 **`NEXT_PUBLIC_API_BASE_URL`** 且填错或未 Redeploy，可**删除**该变量，避免与方式 A 混用；保留也可以，代码会**优先**使用 `NEXT_PUBLIC_*` 直连。

**登录仍 500 时**：在浏览器 **Network** 里点开 `login` → **Response**，看 JSON 是「无法连接后端」（本代理 `502`）还是 FastAPI 的 `detail`。Render **免费实例休眠**时，**首次**请求可能超过 **Vercel Hobby Serverless 默认约 10s**，会在 Vercel 侧超时并表现为 **500/504**。可先新开标签访问 `https://<你的后端>.onrender.com/healthz` **唤醒**后再登录；或改用上面的 **`NEXT_PUBLIC_API_BASE_URL` 直连**（由浏览器长等冷启动，不受 Vercel 函数时长限制）。

### 方式 B：`NEXT_PUBLIC_API_BASE_URL` 直连后端

1. 新增 **`NEXT_PUBLIC_API_BASE_URL`** = `https://你的后端.onrender.com/api/v1`（完整前缀）。
2. **必须 Redeploy**，否则客户端 JS 仍是旧的 `localhost`。
3. Render 上 **`APP_CORS_ORIGINS`** 需包含 `https://你的项目.vercel.app`。

### Favicon 404

仓库已提供 **`frontend/public/favicon.svg`**，并由 **`next.config.js`** 的 rewrite 将 **`/favicon.ico`** 指到该 SVG；若线上仍 404，多半是**未部署最新代码**，请合并最新提交后再 Deploy。

本地可参考 `frontend/.env.example` 复制为 `frontend/.env.local`。

### Render 后端：登录 500 / `Internal Server Error`

1. **数据库连接**：在 Render 打开 **PostgreSQL（如 ai-tp-420-db）**，复制 **Internal Database URL**，加到 **Web Service（ai-tp-420-backend）→ Environment** 中的 **`DATABASE_URL`**（若已自动注入可省略）。后端代码会**优先使用 `DATABASE_URL`**，并自动改为 `postgresql+psycopg://` 以匹配当前 SQLAlchemy 驱动。  
2. **迁移**：首次部署需在容器/启动命令中执行 **`alembic upgrade head`**（或等价迁移），否则没有 `users` 表等也会报错。  
3. 仍失败时看 **ai-tp-420-backend → Logs** 里的 Python Traceback。

---

## 关键目录

```
.
├── docker-compose.yml      # 一键编排所有服务
├── Makefile                # 常用命令
├── .env.example            # 环境变量模板
├── docker/init-db.sql      # pgvector 扩展初始化
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── core/                   # 配置、DB、鉴权、依赖注入
│   │   ├── models/                 # SQLAlchemy 数据模型
│   │   ├── schemas/                # Pydantic 请求/响应模型
│   │   ├── api/v1/                 # REST 路由
│   │   │   ├── auth.py             #   认证
│   │   │   ├── courses.py          #   课程 + 课件上传 + RAG 问答
│   │   │   ├── questions.py        #   题库 + AI 出题
│   │   │   ├── exams.py            #   考试 + 作答 + 判分
│   │   │   └── records.py          #   学习记录 + 数据看板
│   │   ├── services/
│   │   │   ├── parser/             # Word/PDF/PPT/Excel 解析器（统一成 ParsedDocument）
│   │   │   ├── ai/                 # AI Provider 抽象层 + Prompt 模板
│   │   │   ├── rag/                # 分块、向量化、检索
│   │   │   ├── question_service.py # 出题 + 判分
│   │   │   ├── exam_service.py     # 抽题 + 考试流程
│   │   │   └── storage.py          # MinIO/S3 封装
│   │   └── workers/                # Celery 异步任务
│   ├── alembic/                    # 数据库迁移
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    ├── src/
    │   ├── app/
    │   │   ├── login/              # 登录/注册
    │   │   ├── dashboard/          # 学员端：概览/课程/考试/记录
    │   │   └── admin/              # 管理端：课程管理/课件上传/题库/考试
    │   ├── components/             # UI 组件（Button/Card/Input/AppShell）
    │   ├── lib/api.ts              # API 客户端
    │   ├── lib/auth-store.ts       # Zustand 登录态
    │   └── types/api.ts            # 后端 API 类型定义
    ├── package.json
    └── Dockerfile
```

---

## 切换 AI 提供商

只需改 `.env`，代码零改动：

```bash
# DeepSeek（默认，性价比最高）
AI_PROVIDER=deepseek
AI_MODEL_CHAT=deepseek-chat
DEEPSEEK_API_KEY=sk-xxx
DASHSCOPE_API_KEY=sk-xxx        # Embedding 走通义，DeepSeek 没有 embedding

# 通义千问（全家桶）
AI_PROVIDER=qwen
AI_MODEL_CHAT=qwen-plus
AI_MODEL_EMBEDDING=text-embedding-v2
DASHSCOPE_API_KEY=sk-xxx

# OpenAI
AI_PROVIDER=openai
AI_MODEL_CHAT=gpt-4o-mini
AI_MODEL_EMBEDDING=text-embedding-3-small
OPENAI_API_KEY=sk-xxx

# 自托管 vLLM/Ollama（私有化部署）
AI_PROVIDER=custom
AI_MODEL_CHAT=Qwen2.5-14B-Instruct
AI_MODEL_EMBEDDING=bge-m3
OPENAI_BASE_URL=http://your-vllm-host:8000/v1
OPENAI_API_KEY=any-placeholder
```

⚠️ 如果切换 embedding 模型维度不同（默认 1536），需要同步修改 `.env` 里的 `EMBEDDING_DIM` 并重建数据库（切片表的 vector 列长度固定）。

---

## 后续 Roadmap（按优先级）

- [ ] **Phase 7 顾客画像增强**：预设典型画像模板 + 管理员可配置画像库 + 训练模式（AI 扮演客户对话）
- [ ] **Phase 8 音视频解析**：接入 faster-whisper 或阿里 Paraformer 做 ASR 转写，视频自动切分 + 字幕对齐
- [ ] **Phase 9 流式问答**：后端 SSE 流式输出 + 前端打字机效果
- [ ] **题库人工编辑界面**：不仅看，还能改
- [ ] **考试防作弊升级**：切屏强制交卷 + 摄像头抓拍（可选）+ 随机变题
- [ ] **部门看板**：Manager 角色看本部门学员数据
- [ ] **证书系统**：通过考试自动生成电子证书
- [ ] **PWA**：可添加到手机桌面，离线缓存课程大纲
- [ ] **生产部署指南**：K8s Helm Chart / 腾讯云 TKE / 阿里云 ACK

---

## 常见问题

**Q: 上传后长时间卡在 parsing 状态？**
A: 查看 worker 日志 `docker compose logs worker`。常见原因：AI Key 无效（embedding 调用失败）、文件损坏、Celery 还没起来。

**Q: 扫描版 PDF（图片 PDF）能用吗？**
A: 可以。系统会先尝试文字层解析；若未提取到正文，会自动触发 OCR（默认 `chi_sim+eng`）再切片。可在 `.env` 调整：
`PDF_OCR_FALLBACK_ENABLED`、`PDF_OCR_LANG`、`PDF_OCR_DPI`、`PDF_OCR_MAX_PAGES`。

**Q: pgvector HNSW 索引报错？**
A: 需要 pgvector >= 0.5.0。本项目使用的镜像 `pgvector/pgvector:pg16` 自带 0.7。若升级现有数据库，执行 `ALTER EXTENSION vector UPDATE;`。

**Q: 能不能彻底离线部署？**
A: 可以。把 AI_PROVIDER 改为 `custom`，指向本地 vLLM 部署的 Qwen2.5 + BGE-M3；所有其他组件（Postgres/Redis/MinIO/前后端）都是容器化可离线。

**Q: 怎么支持多租户（SaaS 场景）？**
A: 当前是单租户。扩展到 SaaS 需要：
  1. 加 `tenants` 表，所有业务表加 `tenant_id` 外键与索引；
  2. 鉴权 JWT 里携带 tenant_id，API 自动按租户过滤；
  3. 对象存储按 tenant 前缀隔离。
  预计 3-5 天工作量。

---

## 许可证

内部项目，暂未开源许可。
