export type UserRole =
  | "admin"
  | "manager"
  | "editor"
  | "reviewer"
  | "publisher"
  | "learner";

export interface User {
  id: number;
  email: string;
  name: string;
  role: UserRole;
  department: string | null;
  avatar_url: string | null;
}

export type CourseStatus = "draft" | "processing" | "ready" | "archived";
export type MaterialType =
  | "word" | "pdf" | "ppt" | "excel" | "video" | "audio" | "markdown" | "other";

export interface Course {
  id: number;
  title: string;
  description: string | null;
  cover_url: string | null;
  category: string | null;
  tags: string[];
  knowledge_space_id: number | null;
  status: CourseStatus;
  created_at: string;
  updated_at: string;
}

export interface Material {
  id: number;
  filename: string;
  material_type: MaterialType;
  parse_status: string; // pending | parsing | parsed | failed
  parse_error: string | null;
  size_bytes: number;
  /** 含 parse_progress(0–100)、parse_stage、chunks、sections 等 */
  meta: Record<string, unknown>;
  created_at: string;
}

export interface CourseDetail extends Course {
  materials: Material[];
}

export type KnowledgeSpaceStatus = "active" | "archived";
export type KnowledgeDocumentStatus = "draft" | "in_review" | "published" | "archived";
export type KnowledgeRevisionStatus =
  | "draft"
  | "in_review"
  | "approved"
  | "rejected"
  | "published"
  | "archived";
export type KnowledgeConflictStatus = "open" | "resolved" | "ignored";
export type KnowledgeConflictType =
  | "title_duplicate"
  | "content_conflict"
  | "policy_conflict"
  | "manual";

export interface KnowledgeSpace {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  category: string | null;
  tags: string[];
  status: KnowledgeSpaceStatus;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocument {
  id: number;
  space_id: number;
  title: string;
  slug: string;
  path_slug: string;
  parent_id: number | null;
  is_redirect: boolean;
  redirect_document_id: number | null;
  summary: string | null;
  category: string | null;
  tags: string[];
  status: KnowledgeDocumentStatus;
  current_revision_id: number | null;
  published_revision_id: number | null;
  assigned_editor_id: number | null;
  assigned_reviewer_id: number | null;
  assigned_publisher_id: number | null;
  source_course_id: number | null;
  source_material_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeRevision {
  id: number;
  document_id: number;
  version_no: number;
  status: KnowledgeRevisionStatus;
  title: string;
  summary: string | null;
  category: string | null;
  tags: string[];
  markdown_content: string;
  outline: Array<Record<string, unknown>>;
  ai_meta: Record<string, unknown>;
  change_note: string | null;
  review_comment: string | null;
  created_by: number;
  submitted_by: number | null;
  reviewed_by: number | null;
  published_by: number | null;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
  reviewed_at: string | null;
  published_at: string | null;
}

export interface KnowledgeSourceLink {
  id: number;
  document_id: number;
  revision_id: number;
  source_kind: string;
  course_id: number | null;
  material_id: number | null;
  chunk_id: number | null;
  similarity: number | null;
  note: string | null;
  created_at: string;
}

export interface KnowledgeConflict {
  id: number;
  document_id: number;
  draft_revision_id: number;
  published_revision_id: number | null;
  conflict_type: KnowledgeConflictType;
  status: KnowledgeConflictStatus;
  title: string;
  detail: string | null;
  existing_excerpt: string | null;
  incoming_excerpt: string | null;
  resolution_kind: string | null;
  resolved_by: number | null;
  resolved_at: string | null;
  created_at: string;
}

export interface KnowledgeDocumentDetail extends KnowledgeDocument {
  current_revision: KnowledgeRevision | null;
  published_revision: KnowledgeRevision | null;
  revisions: KnowledgeRevision[];
  conflicts: KnowledgeConflict[];
  sources: KnowledgeSourceLink[];
}

export interface KnowledgeTreeNode {
  id: number;
  title: string;
  path_slug: string;
  parent_id: number | null;
  is_redirect: boolean;
  status: KnowledgeDocumentStatus;
}

export interface AskResponse {
  answer: string;
  answer_id: string; // 后端生成的 uuid，用于满意度反馈
  sources: Array<{
    index: number; // 与答案中的 [S{index}] 对应
    chunk_id: number;
    chapter: string | null;
    wiki_path?: string | null;
    wiki_section?: string | null;
    wiki_section_anchor?: string | null;
    score: number;
    snippet: string;
    citations?: number; // 该片段在本次答案中被引用的次数
  }>;
  queries_used?: string[]; // 本次用于检索的查询变体（含原问题 + 改写）
}

export type QuestionType = "single" | "multiple" | "judge" | "fill" | "short";
export type QuestionDifficulty = "easy" | "medium" | "hard";

export interface Question {
  id: number;
  course_id: number;
  type: QuestionType;
  difficulty: QuestionDifficulty;
  stem: string;
  options: Array<{ key: string; text: string }>;
  knowledge_points: string[];
  answer?: string[];
  explanation?: string | null;
  source?: string;
  reviewed?: boolean;
}

/** 按薄弱知识点复习接口返回（含答案与解析） */
export type QuestionReview = Question & {
  answer: string[];
  explanation: string | null;
};

export interface Exam {
  id: number;
  course_id: number;
  title: string;
  description: string | null;
  duration_minutes: number;
  pass_score: number;
  rules: Record<string, { count: number; score: number }>;
  created_at: string;
}

export type ExamStatus = "in_progress" | "submitted" | "graded" | "expired";

export interface Attempt {
  id: number;
  exam_id: number;
  user_id: number;
  status: ExamStatus;
  score: number | null;
  max_score: number;
  started_at: string;
  submitted_at: string | null;
  graded_at: string | null;
  /** 本次试卷题目数（后端由 question_ids 计算） */
  question_count?: number;
}

export interface AttemptStart {
  attempt: Attempt;
  questions: Question[];
}

export interface AnswerDetail {
  question_id: number;
  stem: string;
  type: string;
  user_answer: string[];
  correct_answer: string[];
  is_correct: boolean | null;
  score: number;
  ai_feedback: string | null;
  explanation: string | null;
}

export interface AttemptResult {
  attempt: Attempt;
  passed: boolean;
  details: AnswerDetail[];
}

export interface DashboardStats {
  total_learning_minutes: number;
  courses_viewed: number;
  exams_taken: number;
  exams_passed: number;
  average_score: number | null;
  recent_records: Array<{
    id: number;
    action: string;
    payload: Record<string, unknown>;
    created_at: string;
  }>;
  weak_knowledge_points: Array<{
    point: string;
    wrong_rate: number;
    attempts: number;
  }>;
}
