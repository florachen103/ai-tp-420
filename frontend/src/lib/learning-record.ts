/** 学习记录 action → 中文标题（列表主标题可复用） */
export const LEARNING_ACTION_LABELS: Record<string, string> = {
  view_course: "查看课程",
  ask_question: "智能问答",
  start_exam: "开始考试",
  submit_exam: "提交考试",
  practice: "练习",
  read_chunk: "阅读章节",
  complete_chapter: "完成章节",
  review_kp_perfect: "薄弱点复习全对",
};

function num(v: unknown): number | null {
  if (typeof v === "number" && !Number.isNaN(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
  }
  return null;
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

/** 将后端 payload 格式化为一句可读说明（不含 JSON） */
export function describeLearningRecordPayload(
  action: string,
  payload: Record<string, unknown>
): string {
  const p = payload || {};

  switch (action) {
    case "view_course": {
      const title = str(p.title);
      return title ? `进入课程「${title}」` : "浏览了课程详情";
    }
    case "ask_question": {
      const q = str(p.question);
      const chunks = Array.isArray(p.chunks) ? p.chunks : [];
      const head = q ? (q.length > 72 ? `${q.slice(0, 72)}…` : q) : "向助手提问";
      return `${head} · 引用知识片段 ${chunks.length} 条`;
    }
    case "start_exam": {
      const title = str(p.exam_title);
      const max = num(p.attempt_max_score);
      const eid = num(p.exam_id);
      const name = title || (eid != null ? `考试编号 ${eid}` : "考试");
      return max != null ? `开始「${name}」· 卷面满分 ${max} 分` : `开始「${name}」`;
    }
    case "submit_exam": {
      const title = str(p.exam_title);
      const score = num(p.score);
      const max = num(p.max_score);
      const passed = p.passed === true;
      const eid = num(p.exam_id);
      const aid = num(p.attempt_id);
      const name = title || (eid != null ? `考试编号 ${eid}` : "考试");
      if (score != null && max != null && max > 0) {
        const pct = Math.round((score / max) * 1000) / 10;
        const passTxt = passed ? "通过" : "未通过";
        const attemptTxt = aid != null ? ` · 作答编号 ${aid}` : "";
        return `「${name}」得分 ${score}/${max}（${pct}%）· ${passTxt}${attemptTxt}`;
      }
      return `提交了「${name}」`;
    }
    case "read_chunk": {
      const cid = num(p.chunk_id);
      return cid != null ? `阅读了知识片段（编号 ${cid}）` : "阅读了课件内容";
    }
    case "complete_chapter": {
      const ch = str(p.chapter) || str(p.title);
      return ch ? `完成章节「${ch}」` : "完成章节学习";
    }
    case "practice": {
      const t = str(p.topic) || str(p.title);
      return t ? `练习：${t}` : "完成练习";
    }
    case "review_kp_perfect": {
      const kp = str(p.knowledge_point);
      const n = num(p.question_count);
      if (kp && n != null) return `薄弱知识点「${kp}」自测全对（${n} 题）`;
      return kp ? `薄弱知识点「${kp}」自测全对` : "薄弱知识点自测全对";
    }
    default: {
      const vals = Object.values(p).filter((v) => typeof v === "string" || typeof v === "number");
      if (!vals.length) return "其它学习记录";
      return vals
        .slice(0, 3)
        .map((v) => String(v).slice(0, 44))
        .join(" · ");
    }
  }
}

function stablePayloadJson(p: Record<string, unknown>): string {
  try {
    const keys = Object.keys(p).sort();
    const o: Record<string, unknown> = {};
    for (const k of keys) o[k] = p[k];
    return JSON.stringify(o);
  } catch {
    return "";
  }
}

/** 与后端去重键一致：相同业务含义的多条只保留最新一条 */
export function learningRecordDedupeKey(r: {
  action: string;
  payload: Record<string, unknown>;
  course_id?: number | null;
  id?: number;
}): string {
  const p = r.payload || {};
  const act = r.action;
  if (act === "start_exam") {
    return `start_exam:${p.exam_id}:${p.attempt_max_score}`;
  }
  if (act === "submit_exam") {
    return `submit_exam:${p.attempt_id ?? r.id}`;
  }
  if (act === "ask_question") {
    const q = String(p.question ?? "").slice(0, 160);
    return `ask_question:${q}`;
  }
  if (act === "view_course") {
    return `view_course:${r.course_id ?? ""}:${p.title ?? ""}`;
  }
  if (act === "read_chunk") {
    return `read_chunk:${r.course_id ?? ""}:${p.chunk_id}`;
  }
  if (act === "complete_chapter") {
    return `complete_chapter:${r.course_id ?? ""}:${p.chapter ?? p.title ?? ""}`;
  }
  if (act === "practice") {
    return `practice:${r.course_id ?? ""}:${p.topic ?? p.title ?? ""}`;
  }
  if (act === "review_kp_perfect") {
    const kp = String(p.knowledge_point ?? "").trim().slice(0, 200);
    return `review_kp_perfect:${kp}`;
  }
  return `${act}:${r.course_id ?? ""}:${stablePayloadJson(p as Record<string, unknown>)}`;
}

export function dedupeLearningRecordRows<
  T extends { action: string; payload: Record<string, unknown>; course_id?: number | null; id?: number },
>(rows: T[]): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const r of rows) {
    const k = learningRecordDedupeKey(r);
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(r);
  }
  return out;
}

export function formatLearningDuration(durationSec: number): string | null {
  if (!durationSec || durationSec <= 0) return null;
  if (durationSec < 60) return `停留约 ${durationSec} 秒`;
  const m = Math.round(durationSec / 60);
  return `停留约 ${m} 分钟`;
}
