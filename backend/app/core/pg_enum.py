"""
PostgreSQL 原生枚举与 Python Enum 对齐。

迁移里用的小写字符串（如 admin）建库；SQLAlchemy 默认可能绑定成员名（ADMIN），
导致 psycopg 报错 invalid input value for enum。统一用 values_callable 持久化 .value。
"""
from typing import Any, Type

from sqlalchemy import Enum as SAEnum


def pg_enum(py_enum: Type[Any], pg_type_name: str) -> SAEnum:
    return SAEnum(
        py_enum,
        name=pg_type_name,
        values_callable=lambda cls: [m.value for m in cls],  # type: ignore[arg-type]
        native_enum=True,
    )
