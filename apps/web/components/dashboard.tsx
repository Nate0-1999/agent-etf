"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  CreateIdeaResponse,
  CreateStrategyFromIdeaResponse,
  ManualActionResponse,
  StrategyListItem,
  StrategyListResponse,
  StrategySummaryResponse,
} from "../lib/types";

const DEFAULT_IDEA =
  "Create an equal weight heavy metal investment based on the periodic table: anything element between atomic number 40-52 and 72-80.";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "--";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatLabel(value: string): string {
  return value.replaceAll("_", " ");
}

function buildClarifyPayload(rawIdea: string) {
  return {
    answers: {
      objective: rawIdea,
      allowed_assets: ["etf", "equity", "future"],
      cadence_recommendation: "monthly_review",
    },
  };
}

export function Dashboard() {
  const [ideaText, setIdeaText] = useState(DEFAULT_IDEA);
  const [strategies, setStrategies] = useState<StrategyListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [summary, setSummary] = useState<StrategySummaryResponse | null>(null);
  const [proposal, setProposal] = useState<CreateStrategyFromIdeaResponse | null>(null);
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedStrategy = summary?.strategy ?? null;
  const benchmarkRows = useMemo(() => {
    if (!summary?.latest_backtest) {
      return [];
    }
    return Object.entries(summary.latest_backtest.benchmark_metrics);
  }, [summary]);

  const loadStrategy = useCallback(async (strategyId: string) => {
    const nextSummary = await apiRequest<StrategySummaryResponse>(`/strategies/${strategyId}`);
    setSelectedId(strategyId);
    setSummary(nextSummary);
  }, []);

  const refreshStrategies = useCallback(
    async (preferredId?: string) => {
      const listing = await apiRequest<StrategyListResponse>("/strategies");
      setStrategies(listing.strategies);

      const nextId = preferredId ?? selectedId ?? listing.strategies[0]?.id ?? null;
      if (nextId) {
        await loadStrategy(nextId);
      } else {
        setSelectedId(null);
        setSummary(null);
      }
    },
    [loadStrategy, selectedId],
  );

  useEffect(() => {
    void refreshStrategies();
  }, [refreshStrategies]);

  async function runHeavyMetalsFlow() {
    setIsBusy(true);
    setError(null);
    setProposal(null);
    setActivityLog([]);

    try {
      setActivityLog((current) => [...current, "Create idea"]);
      const idea = await apiRequest<CreateIdeaResponse>("/ideas", {
        method: "POST",
        body: JSON.stringify({
          user_id: "operator",
          raw_idea: ideaText,
        }),
      });

      let readyIdea = idea;
      if (!idea.ready_for_strategy) {
        setActivityLog((current) => [...current, "Clarify missing constraints"]);
        readyIdea = await apiRequest<CreateIdeaResponse>(`/ideas/${idea.idea.id}/clarify`, {
          method: "POST",
          body: JSON.stringify(buildClarifyPayload(ideaText)),
        });
      }

      setActivityLog((current) => [...current, "Create strategy proposal"]);
      const created = await apiRequest<CreateStrategyFromIdeaResponse>(
        `/strategies/from-idea/${readyIdea.idea.id}`,
        {
          method: "POST",
        },
      );
      setProposal(created);

      setActivityLog((current) => [...current, "Run deterministic backtest"]);
      await apiRequest(`/strategies/${created.strategy.id}/backtest`, {
        method: "POST",
        body: JSON.stringify({ min_years: 10, override_min_history: false }),
      });

      setActivityLog((current) => [...current, "Prepare rebalance approval bundle"]);
      await apiRequest<ManualActionResponse>(`/strategies/${created.strategy.id}/manual-rebalance`, {
        method: "POST",
      });

      setActivityLog((current) => [...current, "Load strategy dossier"]);
      await refreshStrategies(created.strategy.id);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Unknown error";
      setError(message);
    } finally {
      setIsBusy(false);
    }
  }

  async function approveDraft() {
    if (!selectedStrategy || selectedStrategy.status !== "draft") {
      return;
    }

    setIsBusy(true);
    setError(null);
    try {
      await apiRequest(`/strategies/${selectedStrategy.id}/approve-create`, {
        method: "POST",
      });
      await refreshStrategies(selectedStrategy.id);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Unknown error";
      setError(message);
    } finally {
      setIsBusy(false);
    }
  }

  async function refreshRebalancePreview() {
    if (!selectedStrategy) {
      return;
    }

    setIsBusy(true);
    setError(null);
    try {
      await apiRequest<ManualActionResponse>(`/strategies/${selectedStrategy.id}/manual-rebalance`, {
        method: "POST",
      });
      await loadStrategy(selectedStrategy.id);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Unknown error";
      setError(message);
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Local strategy workstation</p>
          <h1>Heavy metals strategy generator</h1>
          <p className="lede">
            This local view drives the real API flow: idea intake, deterministic strategy proposal,
            backtest, and approval-bundle preview.
          </p>
        </div>
        <div className="heroStat">
          <span className="heroStatLabel">API target</span>
          <strong>{API_BASE}</strong>
          <span className="heroStatHint">Run the API on localhost before opening this page.</span>
        </div>
      </section>

      <section className="workspace">
        <aside className="rail">
          <div className="panel panel-dark">
            <p className="panelLabel">Idea input</p>
            <textarea
              className="ideaInput"
              value={ideaText}
              onChange={(event) => setIdeaText(event.target.value)}
              rows={7}
            />
            <div className="buttonRow">
              <button className="button button-primary" disabled={isBusy} onClick={runHeavyMetalsFlow}>
                {isBusy ? "Running flow..." : "Build heavy metals draft"}
              </button>
            </div>
            <p className="microcopy">
              The draft remains paused until you explicitly approve it. Rebalance actions still
              require the separate 3-step approval bundle.
            </p>
          </div>

          <div className="panel">
            <p className="panelLabel">Saved strategies</p>
            <div className="strategyList">
              {strategies.length === 0 ? (
                <p className="emptyState">No saved strategies yet. Create the heavy-metals draft first.</p>
              ) : null}
              {strategies.map((strategy) => (
                <button
                  key={strategy.id}
                  className={`strategyCard ${selectedId === strategy.id ? "selected" : ""}`}
                  onClick={() => void loadStrategy(strategy.id)}
                  type="button"
                >
                  <span className="strategyName">{strategy.name}</span>
                  <span className="strategyMeta">
                    <span className={`pill pill-${strategy.status}`}>{strategy.status}</span>
                    <span>{strategy.universe_size} names</span>
                    <span>{formatPercent(strategy.last_backtest_cagr)} CAGR</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <section className="canvas">
          {error ? <div className="errorBanner">{error}</div> : null}

          <div className="grid">
            <section className="panel panel-wide">
              <div className="sectionHeader">
                <div>
                  <p className="panelLabel">Strategy dossier</p>
                  <h2>{selectedStrategy?.name ?? "No strategy selected"}</h2>
                </div>
                <div className="buttonRow">
                  <button
                    className="button button-secondary"
                    disabled={!selectedStrategy || isBusy}
                    onClick={refreshRebalancePreview}
                  >
                    Refresh rebalance preview
                  </button>
                  <button
                    className="button button-primary"
                    disabled={!selectedStrategy || selectedStrategy?.status !== "draft" || isBusy}
                    onClick={approveDraft}
                  >
                    Approve draft
                  </button>
                </div>
              </div>

              {summary?.idea ? (
                <div className="ideaSummary">
                  <p>{summary.idea.raw_idea}</p>
                  <div className="metricStrip">
                    <span>clarity {Math.round(summary.idea.clarity_score * 100)}%</span>
                    <span>{summary.strategy.weighting_method}</span>
                    <span>{summary.idea.cadence_recommendation ?? "cadence pending"}</span>
                    <span>{summary.strategy.rebalance_rule}</span>
                  </div>
                </div>
              ) : (
                <p className="emptyState">
                  The dashboard will populate after you build or select a saved strategy.
                </p>
              )}

              {summary?.proposal_bullets.length ? (
                <ul className="bulletList">
                  {summary.proposal_bullets.map((bullet) => (
                    <li key={bullet}>{bullet}</li>
                  ))}
                </ul>
              ) : null}

              {proposal && proposal.strategy.id === selectedStrategy?.id ? (
                <div className="callout">
                  <strong>Latest proposal run captured in this browser session.</strong>
                  <span>
                    {proposal.audits.length} audit reports were attached to the draft proposal.
                  </span>
                </div>
              ) : null}
            </section>

            <section className="panel">
              <p className="panelLabel">Flow activity</p>
              <ol className="activityList">
                {activityLog.length === 0 ? <li>Waiting for a local run.</li> : null}
                {activityLog.map((entry) => (
                  <li key={entry}>{entry}</li>
                ))}
              </ol>
            </section>

            <section className="panel">
              <p className="panelLabel">Backtest snapshot</p>
              {summary?.latest_backtest ? (
                <div className="metricGrid">
                  <div>
                    <span className="metricLabel">CAGR</span>
                    <strong>{formatPercent(summary.latest_backtest.metrics.cagr)}</strong>
                  </div>
                  <div>
                    <span className="metricLabel">Volatility</span>
                    <strong>{formatPercent(summary.latest_backtest.metrics.volatility)}</strong>
                  </div>
                  <div>
                    <span className="metricLabel">Sharpe</span>
                    <strong>{summary.latest_backtest.metrics.sharpe.toFixed(2)}</strong>
                  </div>
                  <div>
                    <span className="metricLabel">Max drawdown</span>
                    <strong>{formatPercent(summary.latest_backtest.metrics.max_drawdown)}</strong>
                  </div>
                </div>
              ) : (
                <p className="emptyState">No backtest stored for this strategy yet.</p>
              )}
            </section>

            <section className="panel">
              <p className="panelLabel">Benchmarks</p>
              {benchmarkRows.length ? (
                <div className="benchmarkList">
                  {benchmarkRows.map(([name, metrics]) => (
                    <div key={name} className="benchmarkRow">
                      <span>{formatLabel(name)}</span>
                      <span>{formatPercent(metrics.cagr)} CAGR</span>
                      <span>{formatPercent(metrics.max_drawdown)} max DD</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="emptyState">Run or load a backtest to compare against baselines.</p>
              )}
            </section>

            <section className="panel panel-wide">
              <p className="panelLabel">Candidate universe</p>
              <div className="candidateGrid">
                {summary?.strategy.universe.length ? (
                  summary.strategy.universe.map((candidate) => (
                    <article key={candidate.symbol} className="candidateCard">
                      <div className="candidateTop">
                        <div>
                          <h3>{candidate.symbol}</h3>
                          <p>{candidate.name}</p>
                        </div>
                        <span className="scoreTag">{candidate.relevance_score.toFixed(2)}</span>
                      </div>
                      <p className="candidateMeta">
                        {candidate.asset_type} on {candidate.exchange}
                      </p>
                      <p className="candidateBody">{candidate.rationale}</p>
                      <div className="sourceList">
                        {candidate.sources.slice(0, 3).map((source) => (
                          <a key={source} href={source} rel="noreferrer" target="_blank">
                            source
                          </a>
                        ))}
                      </div>
                    </article>
                  ))
                ) : (
                  <p className="emptyState">No strategy universe loaded.</p>
                )}
              </div>
            </section>

            <section className="panel">
              <p className="panelLabel">Audit council</p>
              <div className="auditList">
                {summary?.audits.length ? (
                  summary.audits.map((audit) => (
                    <div key={`${audit.model}-${audit.content_hash}`} className="auditCard">
                      <div className="auditTop">
                        <span>{audit.model}</span>
                        <span className={`pill pill-${audit.verdict === "pass" ? "active" : "paused"}`}>
                          {audit.verdict}
                        </span>
                      </div>
                      <p>{audit.stage}</p>
                      <ul className="bulletList compact">
                        {audit.reasons.map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                    </div>
                  ))
                ) : (
                  <p className="emptyState">No audit reports stored.</p>
                )}
              </div>
            </section>

            <section className="panel">
              <p className="panelLabel">Approval bundle</p>
              {summary?.latest_bundle ? (
                <>
                  <div className="approvalSteps">
                    <span className={summary.latest_bundle.step1_at ? "done" : ""}>1. password + TOTP</span>
                    <span className={summary.latest_bundle.step2_at ? "done" : ""}>2. out-of-band</span>
                    <span className={summary.latest_bundle.step3_at ? "done" : ""}>3. final cooldown confirm</span>
                  </div>
                  <div className="metricStrip">
                    <span>{summary.latest_bundle.action}</span>
                    <span>{summary.latest_bundle.status}</span>
                    <span>{summary.latest_bundle.cooldown_seconds}s cooldown</span>
                  </div>
                  <div className="allocationList">
                    {Object.entries(summary.latest_bundle.target_allocations).map(([symbol, weight]) => (
                      <div key={symbol} className="allocationRow">
                        <span>{symbol}</span>
                        <strong>{formatPercent(weight)}</strong>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="emptyState">No approval bundle exists yet.</p>
              )}
            </section>

            <section className="panel">
              <p className="panelLabel">Paper order preview</p>
              {summary?.latest_order_preview?.orders.length ? (
                <div className="allocationList">
                  {summary.latest_order_preview.orders.map((order) => (
                    <div key={order.symbol} className="allocationRow">
                      <span>{order.symbol}</span>
                      <strong>{formatPercent(order.target_weight)}</strong>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="emptyState">Generate a rebalance preview to see paper orders.</p>
              )}
            </section>

            <section className="panel panel-wide">
              <p className="panelLabel">Deterministic artifact</p>
              {summary?.artifact ? (
                <pre className="codeBlock">{summary.artifact.source_code}</pre>
              ) : (
                <p className="emptyState">No compiled strategy artifact available.</p>
              )}
            </section>
          </div>
        </section>
      </section>
    </main>
  );
}
