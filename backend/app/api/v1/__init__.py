from fastapi import APIRouter

from app.api.v1 import admin, auth, courses, exams, knowledge, questions, records

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(courses.router, prefix="/courses", tags=["课程"])
api_router.include_router(questions.router, prefix="/questions", tags=["题库"])
api_router.include_router(exams.router, prefix="/exams", tags=["考试"])
api_router.include_router(records.router, prefix="/records", tags=["学习记录"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理端"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["知识资产"])
