FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 系统依赖：文件解析、OCR 基础、构建工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libmagic1 \
    libpq-dev \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
