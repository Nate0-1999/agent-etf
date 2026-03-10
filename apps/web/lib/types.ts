export type StrategyStatus = "draft" | "active" | "paused";

export type AuditVerdict = "pass" | "dissent";

export type ApprovalStatus =
  | "pending"
  | "step1_complete"
  | "step2_complete"
  | "approved"
  | "expired"
  | "rejected";

export type CandidateInstrument = {
  symbol: string;
  name: string;
  asset_type: string;
  exchange: string;
  relevance_score: number;
  rationale: string;
  sources: string[];
};

export type IdeaSpec = {
  id: string;
  user_id: string;
  raw_idea: string;
  objective: string | null;
  constraints: Record<string, unknown>;
  exclusions: string[];
  cadence_recommendation: string | null;
  clarity_score: number;
  created_at: string;
};

export type StrategyDefinition = {
  id: string;
  user_id: string;
  idea_id: string;
  name: string;
  status: StrategyStatus;
  universe: CandidateInstrument[];
  weighting_method: string;
  rebalance_rule: string;
  update_rule: string;
  created_at: string;
};

export type StrategyArtifact = {
  strategy_id: string;
  git_commit: string;
  config_hash: string;
  source_code: string;
  generated_at: string;
};

export type AuditReport = {
  stage: string;
  model: string;
  verdict: AuditVerdict;
  reasons: string[];
  content_hash: string;
  created_at: string;
};

export type BacktestMetrics = {
  cagr: number;
  volatility: number;
  sharpe: number;
  max_drawdown: number;
  years_of_history: number;
};

export type BacktestRun = {
  strategy_id: string;
  assumptions: Record<string, string | number | boolean>;
  metrics: BacktestMetrics;
  benchmark_metrics: Record<string, BacktestMetrics>;
  created_at: string;
};

export type ApprovalBundle = {
  id: string;
  strategy_id: string;
  action: string;
  intent_hash: string;
  target_allocations: Record<string, number>;
  cooldown_seconds: number;
  step1_at: string | null;
  step2_at: string | null;
  step3_at: string | null;
  status: ApprovalStatus;
  created_at: string;
};

export type OrderPreviewItem = {
  symbol: string;
  target_weight: number;
  action: string;
};

export type OrderPreview = {
  strategy_id: string;
  action: string;
  orders: OrderPreviewItem[];
};

export type StrategyListItem = {
  id: string;
  name: string;
  status: StrategyStatus;
  created_at: string;
  universe_size: number;
  last_backtest_cagr: number | null;
};

export type StrategyListResponse = {
  strategies: StrategyListItem[];
};

export type StrategySummaryResponse = {
  strategy: StrategyDefinition;
  idea: IdeaSpec | null;
  artifact: StrategyArtifact | null;
  audits: AuditReport[];
  proposal_bullets: string[];
  latest_backtest: BacktestRun | null;
  latest_bundle: ApprovalBundle | null;
  latest_order_preview: OrderPreview | null;
};

export type CreateIdeaResponse = {
  idea: IdeaSpec;
  ready_for_strategy: boolean;
};

export type CreateStrategyFromIdeaResponse = {
  strategy: StrategyDefinition;
  audits: AuditReport[];
  proposal_bullets: string[];
};

export type ManualActionResponse = {
  strategy_id: string;
  action: string;
  loops_attempted: number;
  escalated: boolean;
  escalation_summary: string | null;
  bundle: ApprovalBundle;
};
