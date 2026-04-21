"""
音视频解析占位：MVP 先返回空占位，Phase 8 再接入 ASR。
可选方案：
- 离线：faster-whisper（推荐，开源，中文效果不错，单 GPU 可实时）
- 云端：阿里 Paraformer、腾讯云 ASR、OpenAI Whisper API
"""
from __future__ import annotations

from app.services.parser.base import ParsedDocument, ParsedSection, detect_material_type


def parse_av(file_path: str, filename: str) -> ParsedDocument:
    return ParsedDocument(
        filename=filename,
        material_type=detect_material_type(filename),
        sections=[
            ParsedSection(
                title="待转写",
                content="[音视频待 ASR 转写。请在 Phase 8 接入 faster-whisper 或云 ASR 服务。]",
                order_idx=0,
            )
        ],
        meta={"needs_asr": True},
    )
