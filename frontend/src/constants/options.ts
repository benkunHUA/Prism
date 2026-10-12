export const FEED_TYPES = [
  { label: "RSS", value: "rss" },
  { label: "网页", value: "page" },
];

export const LANGS = [
  { label: "中文", value: "zh" },
  { label: "英文", value: "en" },
  { label: "日文", value: "ja" },
  { label: "俄文", value: "ru" },
  { label: "其他", value: "other" },
];

export const IMPORTANCE_OPTIONS = [
  { label: "高", value: "high" },
  { label: "中", value: "medium" },
  { label: "低", value: "low" },
];

export const IMPORTANCE_COLORS: Record<string, string> = {
  high: "red",
  medium: "gold",
  low: "default",
};

export const WEAPON_LIFECYCLE = ["研发", "测试", "列装", "部署", "出口", "退役"].map((item) => ({
  label: item,
  value: item,
}));

export const LIFECYCLE_COLORS: Record<string, string> = {
  研发: "blue",
  测试: "geekblue",
  列装: "green",
  部署: "cyan",
  出口: "gold",
  退役: "default",
};

export const STANCE_TOPICS = ["对华", "俄乌", "中东", "台海", "贸易", "科技管制", "气候", "能源"].map(
  (item) => ({ label: item, value: item }),
);

export const STANCE_TONES = ["趋严", "缓和", "支持", "反对", "中性", "未定"].map((item) => ({
  label: item,
  value: item,
}));

export const TONE_COLORS: Record<string, string> = {
  趋严: "red",
  缓和: "green",
  支持: "blue",
  反对: "volcano",
  中性: "default",
  未定: "default",
};

export const ASSET_CLASSES = [
  { label: "指数", value: "index" },
  { label: "利率", value: "rate" },
  { label: "外汇", value: "fx" },
  { label: "商品", value: "commodity" },
  { label: "波动率", value: "volatility" },
  { label: "加密资产", value: "crypto" },
];

export const MODERATION_TYPE_LABELS: Record<string, string> = {
  timeline: "事件",
  weapon: "武器",
  stance: "立场",
  indicator: "指标",
};

export const TASK_KIND_LABELS: Record<string, string> = {
  collect: "采集",
  analyze: "分析",
};

export const VERDICT_LABELS: Record<string, { text: string; color: string }> = {
  beat: { text: "好于", color: "green" },
  miss: { text: "不及", color: "red" },
  inline: { text: "持平", color: "default" },
};

export const HEALTH_LABELS: Record<string, { text: string; color: string }> = {
  ok: { text: "正常", color: "green" },
  warn: { text: "慢响应 / 重试中", color: "gold" },
  bad: { text: "失败", color: "red" },
  off: { text: "已停用", color: "default" },
};

export const LOG_STATUS: Record<string, { text: string; color: string }> = {
  success: { text: "成功", color: "green" },
  partial: { text: "部分成功", color: "gold" },
  failed: { text: "失败", color: "red" },
  running: { text: "运行中", color: "blue" },
};

export const TEXT = {
  emptyDefault: "暂无数据，等待采集与分析产出",
  emptyTimeline: (label: string) => `暂无已确认的${label}事件`,
  emptyWeapons: "暂无已确认的武器档案",
  emptyIndicators: "暂无宏观指标数据",
  emptyStances: "暂无议题立场记录",
  emptySnapshots: "暂无行情快照（需在 .env 配置 MARKET_SYMBOLS 后执行采集）",
  emptyReports: "今日报告尚未生成，可先执行采集与分析任务",
  manualCollect: "手动采集",
  moderation: "待确认",
  confirm: "确认",
  edit: "编辑",
  reject: "丢弃",
  save: "保存",
  cancel: "取消",
  refresh: "刷新",
  readMore: "阅读 →",
} as const;
