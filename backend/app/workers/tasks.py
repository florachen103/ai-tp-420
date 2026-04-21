"""
异步任务：与 Celery 集成；解析逻辑在 app.services.material_parse。
"""
from __future__ import annotations

from app.services.material_parse import parse_material_job
from app.workers.celery_app import celery_app


@celery_app.task(name="parse_material", bind=True, max_retries=2)
def parse_material_task(self, material_id: int):
    try:
        parse_material_job(material_id)
    except Exception as e:
        raise self.retry(exc=e, countdown=60) from e
