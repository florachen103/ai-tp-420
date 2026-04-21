-- 启用 pgvector 扩展，用于向量相似度检索
CREATE EXTENSION IF NOT EXISTS vector;
-- 中文全文检索可选扩展（需要 zhparser，生产环境再加）
-- CREATE EXTENSION IF NOT EXISTS zhparser;
