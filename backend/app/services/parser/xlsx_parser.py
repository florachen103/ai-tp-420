"""Excel 解析：每个 sheet 一节，把表格转成 markdown 形式便于 LLM 理解。"""
from __future__ import annotations

import pandas as pd

from app.models.course import MaterialType
from app.services.parser.base import ParsedDocument, ParsedSection


def parse_xlsx(file_path: str, filename: str) -> ParsedDocument:
    sections: list[ParsedSection] = []
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip")
        sections.append(_df_to_section("数据", df, 0))
    else:
        xls = pd.ExcelFile(file_path)
        for i, sheet_name in enumerate(xls.sheet_names):
            df = xls.parse(sheet_name)
            sections.append(_df_to_section(sheet_name, df, i))

    return ParsedDocument(
        filename=filename,
        material_type=MaterialType.EXCEL,
        sections=sections,
        meta={"sheet_count": len(sections)},
    )


def _df_to_section(title: str, df: "pd.DataFrame", order: int) -> ParsedSection:
    # 行数过多则截断，避免把整个订单表灌进 LLM
    preview_rows = 200
    total = len(df)
    head = df.head(preview_rows)
    content = head.to_markdown(index=False) if not head.empty else "(空表)"
    if total > preview_rows:
        content += f"\n\n（共 {total} 行，仅展示前 {preview_rows} 行）"
    return ParsedSection(
        title=f"Sheet: {title}",
        content=content,
        order_idx=order,
        meta={"rows": total, "columns": list(map(str, df.columns))},
    )
