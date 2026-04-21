"""FastAPI 入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings

app = FastAPI(
    title="AI 培训平台 API",
    description="基于 RAG 的企业级在线培训系统（支持课件解析、AI 问答、题目生成、考试判分）",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", tags=["系统"])
def root():
    return {
        "app": "AI 培训平台",
        "version": "0.1.0",
        "env": settings.APP_ENV,
        "docs": "/docs",
    }


@app.get("/healthz", tags=["系统"])
def healthz():
    return {"status": "ok"}
