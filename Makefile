.PHONY: help setup up down logs backend frontend worker migrate db-shell clean

help:
	@echo "常用命令："
	@echo "  make setup     - 首次初始化（拷贝 .env, 拉镜像）"
	@echo "  make up        - 启动所有服务（docker compose up）"
	@echo "  make down      - 停止所有服务"
	@echo "  make logs      - 查看日志"
	@echo "  make backend   - 只跑后端 (本地非 docker)"
	@echo "  make frontend  - 只跑前端 (本地非 docker)"
	@echo "  make worker    - 只跑 celery worker (本地)"
	@echo "  make migrate   - 生成/应用数据库迁移"

setup:
	@test -f .env || cp .env.example .env
	@echo "✓ .env 已就绪（记得填写 DEEPSEEK_API_KEY / DASHSCOPE_API_KEY）"
	docker compose pull

up:
	docker compose up -d
	@echo ""
	@echo "✓ 启动完成："
	@echo "  - 前端:       http://localhost:3000"
	@echo "  - 后端 API:   http://localhost:8000/docs"
	@echo "  - MinIO 控制台: http://localhost:9001 (minioadmin/minioadmin)"

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

worker:
	cd backend && celery -A app.workers.celery_app worker --loglevel=info

migrate:
	cd backend && alembic upgrade head

db-shell:
	docker compose exec postgres psql -U training -d training

clean:
	docker compose down -v
	rm -rf docker/data
