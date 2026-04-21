/** 闯关式「场景小片段」：大题库 + 按批次随机抽取，支持「换一换」 */

/** 与课程详情页中 lucide 图标映射一致（扁平 SVG） */
export type ScenarioIconName =
  | "Film"
  | "HelpCircle"
  | "Quote"
  | "AlertTriangle"
  | "Target"
  | "Scale"
  | "Repeat2"
  | "Timer"
  | "Users"
  | "MessageSquare"
  | "LayoutList"
  | "Puzzle"
  | "Handshake"
  | "BookOpen"
  | "ListChecks"
  | "SlidersHorizontal";

export type ScenarioCard = {
  id: string;
  /** 扁平化图标名，由页面映射为 lucide-react 组件 */
  icon: ScenarioIconName;
  title: string;
  subtitle: string;
  /** 发给 /ask 的 question 正文 */
  question: string;
};

type ScenarioDef = {
  key: string;
  icon: ScenarioIconName;
  title: string;
  subtitle: string;
  buildQuestion: (t: string, d: string) => string;
};

function withDesc(d: string, tail: string) {
  return d ? `${tail}（课程简介供联想：${d}）` : tail;
}

/** 全部可轮换的场景模板（数量需明显大于每批展示条数） */
const SCENARIO_POOL: ScenarioDef[] = [
  {
    key: "open20",
    icon: "Film",
    title: "二十秒开场",
    subtitle: "第一次怎么开口",
    buildQuestion: (t, d) =>
      withDesc(
        d,
        `用课程「${t}」里的知识点，给我一个「第一次向顾客开口」的口语版二十秒话术，只要一段话，不要分点论述。`
      ),
  },
  {
    key: "price",
    icon: "HelpCircle",
    title: "顾客嫌贵",
    subtitle: "一句接话与转折",
    buildQuestion: (t, d) =>
      withDesc(
        d,
        `场景：顾客说「太贵了」。请只根据课程「${t}」的资料，给我「一句接话 + 一句转折」共两句，像台词一样短。`
      ),
  },
  {
    key: "golden",
    icon: "Quote",
    title: "今日金句",
    subtitle: "记住一句就够",
    buildQuestion: (t, d) =>
      withDesc(d, `从课程「${t}」里提炼「今天只要记住的一句金句」+ 八字以内的记忆口诀，不要超过三行。`),
  },
  {
    key: "trap",
    icon: "AlertTriangle",
    title: "易踩坑",
    subtitle: "一个反例就够",
    buildQuestion: (t, d) =>
      withDesc(
        d,
        `根据课程「${t}」，只讲「一个最常见的错误说法」+「改成怎么说更好」，各不超过十五字，像错题本一样短。`
      ),
  },
  {
    key: "quiz",
    icon: "Target",
    title: "快问快答",
    subtitle: "考我一个点",
    buildQuestion: (t, d) =>
      withDesc(
        d,
        `基于课程「${t}」出一个超短情景判断：给我一句情境 + 两个选项（甲、乙各不超过十二字），再揭示正确选项和一句理由（理由不超过二十字）。`
      ),
  },
  {
    key: "compare",
    icon: "Scale",
    title: "和竞品比",
    subtitle: "三句话不贬对手",
    buildQuestion: (t, d) =>
      withDesc(
        d,
        `只依据课程「${t}」，教我「不贬低竞品」的前提下，用三句话说明我们的优势，每句不超过十八字。`
      ),
  },
  {
    key: "repeat",
    icon: "Repeat2",
    title: "老顾客复购",
    subtitle: "一句唤醒需求",
    buildQuestion: (t, d) =>
      withDesc(d, `场景：老顾客路过柜台。请用课程「${t}」的知识，写一句自然唤醒复购的话，不超过二十五字。`),
  },
  {
    key: "busy",
    icon: "Timer",
    title: "对方很忙",
    subtitle: "先征得十秒钟",
    buildQuestion: (t, d) =>
      withDesc(
        d,
        `场景：对方说「我很忙」。请根据课程「${t}」，给我「征得十秒钟」的两句口语，每句不超过十五字。`
      ),
  },
  {
    key: "family",
    icon: "Users",
    title: "帮家人问",
    subtitle: "温和专业一句",
    buildQuestion: (t, d) =>
      withDesc(
        d,
        `场景：顾客替家人咨询。请用课程「${t}」写「一句安抚 + 一句专业建议」，共两句，每句不超过十八字。`
      ),
  },
  {
    key: "wechat",
    icon: "MessageSquare",
    title: "线上私聊",
    subtitle: "不骚扰的开场",
    buildQuestion: (t, d) =>
      withDesc(
        d,
        `场景：第一次在微信私聊潜在客户。请依据课程「${t}」写不超过三行的开场，语气克制、不推销感。`
      ),
  },
  {
    key: "summary",
    icon: "LayoutList",
    title: "一分钟讲清",
    subtitle: "给完全外行",
    buildQuestion: (t, d) =>
      withDesc(d, `请用课程「${t}」的知识，给「完全外行」用一分钟讲清核心价值：只要一个小提纲，四行以内。`),
  },
  {
    key: "myth",
    icon: "Puzzle",
    title: "破除误解",
    subtitle: "纠正一个谣言",
    buildQuestion: (t, d) =>
      withDesc(
        d,
        `根据课程「${t}」，选一个常见误解，用「一句澄清 + 一句正确说法」纠正，每句不超过二十字。`
      ),
  },
  {
    key: "close",
    icon: "Handshake",
    title: "体面收尾",
    subtitle: "留个好印象",
    buildQuestion: (t, d) =>
      withDesc(d, `场景：今天没成交。请用课程「${t}」写「体面收尾」的三句告别语，每句不超过十二字。`),
  },
  {
    key: "story",
    icon: "BookOpen",
    title: "小故事开场",
    subtitle: "拉近距离",
    buildQuestion: (t, d) =>
      withDesc(
        d,
        `请用课程「${t}」里的信息，编一个「二十秒内讲完」的微型故事开场（虚构情节要标注为举例），总共不超过四行。`
      ),
  },
  {
    key: "checklist",
    icon: "ListChecks",
    title: "出门前检查",
    subtitle: "三个自检点",
    buildQuestion: (t, d) =>
      withDesc(d, `根据课程「${t}」，列出「见顾客前」三个自检点，每条不超过十二字，不要展开论述。`),
  },
  {
    key: "tone",
    icon: "SlidersHorizontal",
    title: "语气太硬",
    subtitle: "软化说法",
    buildQuestion: (t, d) =>
      withDesc(
        d,
        `我把一句话说得太硬了。请用课程「${t}」教我：给原句 + 软化后的说法，各不超过十八字，不加分析。`
      ),
  },
];

function mulberry32(seed: number) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffleSeeded<T>(items: T[], seed: number): T[] {
  const a = [...items];
  const rand = mulberry32(seed >>> 0);
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/**
 * @param batchIndex 每点一次「换一换」+1，会换一批不重复优先的场景
 * @param count 每批卡片数量（默认 5）
 */
export function pickScenarioCards(
  courseTitle: string,
  description: string | null | undefined,
  batchIndex: number,
  count = 5
): ScenarioCard[] {
  const t = courseTitle.trim() || "本课程";
  const d = (description || "").trim().slice(0, 60);
  const seed =
    (batchIndex + 1) * 1009 +
    t.length * 17 +
    (d.length % 97) * 13 +
    (t.codePointAt(0) ?? 0);
  const shuffled = shuffleSeeded(SCENARIO_POOL, seed);
  const slice = shuffled.slice(0, Math.min(count, shuffled.length));
  return slice.map((def, i) => ({
    id: `${def.key}-b${batchIndex}-${i}`,
    icon: def.icon,
    title: def.title,
    subtitle: def.subtitle,
    question: def.buildQuestion(t, d),
  }));
}

/** @deprecated 使用 pickScenarioCards */
export function buildScenarioCards(courseTitle: string, description?: string | null): ScenarioCard[] {
  return pickScenarioCards(courseTitle, description, 0, 5);
}
