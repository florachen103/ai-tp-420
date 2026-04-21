/** 界面展示用中文（避免直接渲染后端枚举英文值） */

/** 课程状态（与后端 CourseStatus 枚举值一致） */
export const COURSE_STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  processing: "解析中",
  ready: "可学习",
  archived: "已归档",
};

export function labelCourseStatus(s: string): string {
  return COURSE_STATUS_LABEL[s] ?? "其它状态";
}

export const KNOWLEDGE_DOCUMENT_STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  in_review: "审核中",
  approved: "已通过",
  rejected: "已驳回",
  published: "已发布",
  archived: "已归档",
};

export function labelKnowledgeStatus(s: string): string {
  return KNOWLEDGE_DOCUMENT_STATUS_LABEL[s] ?? "其它状态";
}

export const KNOWLEDGE_CONFLICT_STATUS_LABEL: Record<string, string> = {
  open: "待处理",
  resolved: "已解决",
  ignored: "已忽略",
};

export function labelKnowledgeConflictStatus(s: string): string {
  return KNOWLEDGE_CONFLICT_STATUS_LABEL[s] ?? "其它状态";
}

export const KNOWLEDGE_CONFLICT_TYPE_LABEL: Record<string, string> = {
  title_duplicate: "标题重复",
  content_conflict: "内容冲突",
  policy_conflict: "策略冲突",
  manual: "人工标记",
};

export function labelKnowledgeConflictType(t: string): string {
  return KNOWLEDGE_CONFLICT_TYPE_LABEL[t] ?? "其它类型";
}

/** 知识空间状态（预留：列表若展示则统一中文） */
export const KNOWLEDGE_SPACE_STATUS_LABEL: Record<string, string> = {
  active: "使用中",
  archived: "已归档",
};

export function labelKnowledgeSpaceStatus(s: string): string {
  return KNOWLEDGE_SPACE_STATUS_LABEL[s] ?? "其它状态";
}

export const PARSE_STATUS_LABEL: Record<string, string> = {
  pending: "排队中",
  parsing: "解析中",
  parsed: "解析完成",
  failed: "解析失败",
};

/** 解析阶段里偶发的英文占位（后端以中文为主，此处兜底） */
const PARSE_STAGE_EN_FALLBACK: Record<string, string> = {
  queued: "排队中",
  downloading: "下载中",
  extracting: "正文提取中",
  embedding: "向量化中",
  indexing: "写入索引中",
  parsing: "解析中",
  pending: "排队中",
  failed: "解析失败",
  done: "解析完成",
  complete: "解析完成",
  completed: "解析完成",
};

export function labelParseStatus(s: string): string {
  return PARSE_STATUS_LABEL[s] ?? "处理中";
}

/** 课件列表行：优先展示 parse_stage（多为中文），否则用 parse_status 映射 */
export function labelMaterialParseLine(
  meta: Record<string, unknown> | undefined | null,
  parseStatus: string
): string {
  const raw = meta?.parse_stage;
  const stage = typeof raw === "string" ? raw.trim() : "";
  if (stage) {
    if (/[\u4e00-\u9fff]/.test(stage)) return stage;
    const mapped = PARSE_STAGE_EN_FALLBACK[stage.toLowerCase()];
    if (mapped) return mapped;
    return labelParseStatus(parseStatus);
  }
  return labelParseStatus(parseStatus);
}

export function labelQuestionType(t: string): string {
  return QUESTION_TYPE_LABEL[t] ?? "题目";
}

export function labelQuestionDifficulty(d: string): string {
  return QUESTION_DIFFICULTY_LABEL[d] ?? "难度";
}

/** 差评自检报告：建议所属领域（后端可能返回英文 key） */
export const AUDIT_RECOMMENDATION_AREA_BADGE: Record<
  string,
  { label: string; className: string }
> = {
  prompt: { label: "提示词", className: "bg-sky-50 text-sky-700 border-sky-200" },
  retrieval: { label: "检索", className: "bg-violet-50 text-violet-700 border-violet-200" },
  chunking: { label: "切块", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  corpus: { label: "语料", className: "bg-amber-50 text-amber-700 border-amber-200" },
};

export function labelAuditRecommendationArea(area: string | undefined | null): string {
  if (!area) return "其它";
  return AUDIT_RECOMMENDATION_AREA_BADGE[area]?.label ?? "其它";
}

export const MATERIAL_TYPE_LABEL: Record<string, string> = {
  word: "文档",
  pdf: "PDF 文档",
  ppt: "演示稿",
  excel: "表格",
  video: "视频",
  audio: "音频",
  markdown: "文稿",
  other: "资料",
};

export function labelMaterialType(t: string): string {
  return MATERIAL_TYPE_LABEL[t] ?? "资料";
}

export const QUESTION_TYPE_LABEL: Record<string, string> = {
  single: "单选题",
  multiple: "多选题",
  judge: "判断题",
  fill: "填空题",
  short: "简答题",
};

export const QUESTION_DIFFICULTY_LABEL: Record<string, string> = {
  easy: "简单",
  medium: "中等",
  hard: "较难",
};

export const ATTEMPT_STATUS_LABEL: Record<string, string> = {
  in_progress: "作答中",
  submitted: "待批改",
  graded: "已出分",
  expired: "已过期",
};

export function labelAttemptStatus(s: string): string {
  return ATTEMPT_STATUS_LABEL[s] ?? "其它状态";
}
