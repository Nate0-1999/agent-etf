export type StrategyStatus = "draft" | "active" | "paused";
export type ApprovalAction = "create" | "rebalance" | "update";
export type ApprovalStatus =
  | "pending"
  | "step1_complete"
  | "step2_complete"
  | "approved"
  | "expired"
  | "rejected";
export type DecisionTileStatus =
  | "empty"
  | "in_progress"
  | "resolved"
  | "needs_user_input"
  | "blocked_by_council";
export type IdeationSessionStatus = "drafting" | "ready_to_convert" | "converted";
export type MessageRole = "system" | "user" | "assistant" | "council";
export type ModelProposalStatus = "pending" | "approved" | "superseded";

export type AuditReport = {
  stage: string;
  model: string;
  verdict: "pass" | "dissent";
  reasons: string[];
  content_hash: string;
  created_at: string;
};

export type DecisionTile = {
  key: string;
  title: string;
  status: DecisionTileStatus;
  summary: string;
  bullets: string[];
  updated_at: string;
};

export type CouncilSummary = {
  stage: string;
  headline: string;
  passed: boolean;
  reports: AuditReport[];
  active_model_set_id: string | null;
  updated_at: string;
};

export type IdeationMessage = {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
};

export type IdeationSession = {
  id: string;
  user_id: string;
  title: string;
  status: IdeationSessionStatus;
  raw_thesis: string;
  decision_tiles: DecisionTile[];
  council_summary: CouncilSummary | null;
  linked_index_id: string | null;
  created_at: string;
  updated_at: string;
};

export type IdeationSessionDetailResponse = {
  session: IdeationSession;
  messages: IdeationMessage[];
};

export type IdeationSessionListResponse = {
  sessions: IdeationSession[];
};

export type HoldingsSummary = {
  symbol: string;
  name: string;
  weight: number;
  asset_type: string;
  exchange: string;
};

export type BacktestMetrics = {
  cagr: number;
  volatility: number;
  sharpe: number;
  max_drawdown: number;
  years_of_history: number;
};

export type OrderPreviewItem = {
  symbol: string;
  target_weight: number;
  action: string;
};

export type OrderPreviewResponse = {
  strategy_id: string;
  action: string;
  orders: OrderPreviewItem[];
};

export type ApprovalBundle = {
  id: string;
  strategy_id: string;
  action: ApprovalAction;
  intent_hash: string;
  target_allocations: Record<string, number>;
  cooldown_seconds: number;
  step1_at: string | null;
  step2_at: string | null;
  step3_at: string | null;
  status: ApprovalStatus;
  created_at: string;
};

export type TimeframePerformance = {
  timeframe: string;
  strategy_return: number;
  benchmark_returns: Record<string, number>;
};

export type IndexSummary = {
  id: string;
  strategy_id: string;
  name: string;
  status: StrategyStatus;
  thesis_summary: string;
  holdings_count: number;
  rebalance_cadence: string;
  created_at: string;
  latest_cagr: number | null;
};

export type IndexDetail = {
  id: string;
  strategy_id: string;
  name: string;
  status: StrategyStatus;
  thesis_summary: string;
  holdings: HoldingsSummary[];
  performance: TimeframePerformance[];
  benchmark_summary: Record<string, BacktestMetrics>;
  rebalance_cadence: string;
  approval_status: ApprovalStatus | null;
  council_summary: CouncilSummary | null;
  created_at: string;
  updated_at: string;
};

export type IndexListResponse = {
  indexes: IndexSummary[];
};

export type ConvertIdeationSessionResponse = {
  session: IdeationSession;
  index: IndexDetail;
};

export type ModelCatalogEntry = {
  id: string;
  provider: "openai" | "anthropic" | "google";
  family: string;
  label: string;
  openrouter_slug: string;
  official_doc_url: string;
  is_stable: boolean;
  supports_text: boolean;
  discovered_at: string;
};

export type ApprovedModelSet = {
  id: string;
  openai_model: ModelCatalogEntry;
  anthropic_model: ModelCatalogEntry;
  google_model: ModelCatalogEntry;
  approved_at: string;
  status: string;
};

export type PendingModelSetProposal = {
  id: string;
  current_set_id: string | null;
  proposed_set: ApprovedModelSet;
  rationale: string;
  status: ModelProposalStatus;
  created_at: string;
  approved_at: string | null;
};

export type CurrentModelSetResponse = {
  model_set: ApprovedModelSet;
};

export type ModelProposalListResponse = {
  proposals: PendingModelSetProposal[];
};

export type ModelRefreshResponse = {
  catalog: ModelCatalogEntry[];
  current: ApprovedModelSet;
  proposal: PendingModelSetProposal | null;
};

export type ManualActionResponse = {
  strategy_id: string;
  action: ApprovalAction;
  loops_attempted: number;
  escalated: boolean;
  escalation_summary: string | null;
  bundle: ApprovalBundle;
};

export type ApprovalBundleResponse = {
  bundle: ApprovalBundle;
};

export type StrategySummaryResponse = {
  strategy: {
    id: string;
    name: string;
    status: StrategyStatus;
    weighting_method: string;
    rebalance_rule: string;
    update_rule: string;
  };
  latest_bundle: ApprovalBundle | null;
  latest_order_preview: OrderPreviewResponse | null;
};

export type DevResetResponse = {
  cleared: boolean;
  message: string;
};
