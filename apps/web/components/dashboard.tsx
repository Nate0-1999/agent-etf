"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  ApprovedModelSet,
  ConvertIdeationSessionResponse,
  CouncilSummary,
  CurrentModelSetResponse,
  DevResetResponse,
  IdeationMessage,
  IdeationSession,
  IdeationSessionDetailResponse,
  IdeationSessionListResponse,
  IndexDetail,
  IndexListResponse,
  IndexSummary,
  ModelProposalListResponse,
  ModelRefreshResponse,
  PendingModelSetProposal,
  TimeframePerformance,
} from "../lib/types";
import {
  appendApiEvent,
  getTestRunId,
  publishVerificationState,
} from "../lib/verification";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const SAVED_INDEXES_TAB = "saved-indexes";
const OPEN_TABS_KEY = "agentic-indexing.open-tabs";
const ACTIVE_TAB_KEY = "agentic-indexing.active-tab";

type SessionDetailMap = Record<string, IdeationSessionDetailResponse>;

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(getTestRunId() ? { "X-Test-Run-Id": getTestRunId() ?? "" } : {}),
      ...(init?.headers ?? {}),
    },
  });

  appendApiEvent({
    timestamp: new Date().toISOString(),
    path,
    method: init?.method ?? "GET",
    status: response.status,
    requestId: response.headers.get("X-Request-Id"),
    testRunId: response.headers.get("X-Test-Run-Id") ?? getTestRunId(),
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

function shortTabTitle(value: string): string {
  return value.length > 22 ? `${value.slice(0, 19)}...` : value;
}

function loadStoredTabIds(): string[] {
  if (typeof window === "undefined") {
    return [];
  }
  const raw = window.localStorage.getItem(OPEN_TABS_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === "string") : [];
  } catch {
    return [];
  }
}

function loadStoredActiveTab(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(ACTIVE_TAB_KEY);
}

function persistWorkspace(openSessionIds: string[], activeTab: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(OPEN_TABS_KEY, JSON.stringify(openSessionIds));
  window.localStorage.setItem(ACTIVE_TAB_KEY, activeTab);
}

function sessionStatusLabel(status: IdeationSession["status"]): string {
  return status.replaceAll("_", " ");
}

function performanceRow(timeframe: TimeframePerformance) {
  return Object.entries(timeframe.benchmark_returns).map(([name, value]) => ({
    name,
    value,
  }));
}

function councilCount(summary: CouncilSummary | null): string {
  if (!summary) {
    return "Council idle";
  }
  return `${summary.reports.length} checks`;
}

export function Dashboard() {
  const [sessions, setSessions] = useState<IdeationSession[]>([]);
  const [sessionDetails, setSessionDetails] = useState<SessionDetailMap>({});
  const [openSessionIds, setOpenSessionIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<string>(SAVED_INDEXES_TAB);
  const [indexes, setIndexes] = useState<IndexSummary[]>([]);
  const [selectedIndexId, setSelectedIndexId] = useState<string | null>(null);
  const [indexDetail, setIndexDetail] = useState<IndexDetail | null>(null);
  const [currentModels, setCurrentModels] = useState<ApprovedModelSet | null>(null);
  const [modelProposals, setModelProposals] = useState<PendingModelSetProposal[]>([]);
  const [showModelAdmin, setShowModelAdmin] = useState(false);
  const [expandedCouncilTab, setExpandedCouncilTab] = useState<string | null>(null);
  const [messageDraft, setMessageDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const activeSessionId = activeTab === SAVED_INDEXES_TAB ? null : activeTab;
  const activeSession = activeSessionId ? sessionDetails[activeSessionId]?.session ?? null : null;
  const activeMessages = activeSessionId ? sessionDetails[activeSessionId]?.messages ?? [] : [];

  const openSessions = useMemo(() => {
    const byId = new Map(sessions.map((session) => [session.id, session]));
    return openSessionIds.map((id) => byId.get(id)).filter((session): session is IdeationSession => Boolean(session));
  }, [openSessionIds, sessions]);

  const selectedIndex = useMemo(
    () => indexes.find((item) => item.id === selectedIndexId) ?? null,
    [indexes, selectedIndexId],
  );

  const refreshModels = useCallback(async () => {
    const [current, proposals] = await Promise.all([
      apiRequest<CurrentModelSetResponse>("/models/current"),
      apiRequest<ModelProposalListResponse>("/models/proposals"),
    ]);
    setCurrentModels(current.model_set);
    setModelProposals(proposals.proposals.filter((item) => item.status === "pending"));
  }, []);

  const ensureSessionLoaded = useCallback(async (sessionId: string) => {
    const detail = await apiRequest<IdeationSessionDetailResponse>(`/ideation/sessions/${sessionId}`);
    setSessionDetails((current) => ({ ...current, [sessionId]: detail }));
    setSessions((current) => {
      const next = current.filter((item) => item.id !== detail.session.id);
      next.unshift(detail.session);
      return next;
    });
    return detail;
  }, []);

  const refreshIndexes = useCallback(async (preferredIndexId?: string) => {
    const listing = await apiRequest<IndexListResponse>("/indexes");
    setIndexes(listing.indexes);

    const nextSelected = preferredIndexId ?? selectedIndexId ?? listing.indexes[0]?.id ?? null;
    setSelectedIndexId(nextSelected);
    if (nextSelected) {
      const detail = await apiRequest<IndexDetail>(`/indexes/${nextSelected}`);
      setIndexDetail(detail);
    } else {
      setIndexDetail(null);
    }
  }, [selectedIndexId]);

  const refreshSessions = useCallback(async () => {
    const listing = await apiRequest<IdeationSessionListResponse>("/ideation/sessions?user_id=operator");
    setSessions(listing.sessions);

    const storedOpen = loadStoredTabIds();
    const availableIds = new Set(listing.sessions.map((session) => session.id));
    const nextOpen = storedOpen.filter((id) => availableIds.has(id));
    setOpenSessionIds(nextOpen);

    const storedActive = loadStoredActiveTab();
    if (storedActive === SAVED_INDEXES_TAB || (storedActive && availableIds.has(storedActive))) {
      setActiveTab(storedActive);
    } else {
      setActiveTab(SAVED_INDEXES_TAB);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshSessions(), refreshIndexes(), refreshModels()]);
  }, [refreshIndexes, refreshModels, refreshSessions]);

  useEffect(() => {
    void refreshAll().catch((nextError) => {
      setError(nextError instanceof Error ? nextError.message : "Failed to load dashboard");
    });
  }, [refreshAll]);

  useEffect(() => {
    persistWorkspace(openSessionIds, activeTab);
  }, [activeTab, openSessionIds]);

  useEffect(() => {
    if (activeSessionId && !sessionDetails[activeSessionId]) {
      void ensureSessionLoaded(activeSessionId).catch((nextError) => {
        setError(nextError instanceof Error ? nextError.message : "Failed to load ideation tab");
      });
    }
  }, [activeSessionId, ensureSessionLoaded, sessionDetails]);

  useEffect(() => {
    publishVerificationState({
      route: activeTab === SAVED_INDEXES_TAB ? "saved-indexes" : "ideation",
      activeTab: activeTab === SAVED_INDEXES_TAB ? SAVED_INDEXES_TAB : "ideation-session",
      openTabs: openSessions.map((session) => session.title),
      savedIndexCount: indexes.length,
      selectedIndexName: selectedIndex?.name ?? indexDetail?.name ?? null,
      showModelAdmin,
      pendingModelProposalCount: modelProposals.length,
      error,
      isBusy,
      session: activeSession
        ? {
            title: activeSession.title,
            status: activeSession.status,
            messageCount: activeMessages.length,
            councilHeadline: activeSession.council_summary?.headline ?? null,
            tileStatuses: Object.fromEntries(
              activeSession.decision_tiles.map((tile) => [tile.key, tile.status]),
            ),
          }
        : null,
    });
  }, [
    activeMessages.length,
    activeSession,
    activeTab,
    error,
    indexDetail,
    indexes.length,
    isBusy,
    modelProposals.length,
    openSessions,
    selectedIndex,
    showModelAdmin,
  ]);

  const createNewIdeaTab = useCallback(async () => {
    setIsBusy(true);
    setError(null);
    try {
      const nextNumber = sessions.length + 1;
      const detail = await apiRequest<IdeationSessionDetailResponse>("/ideation/sessions", {
        method: "POST",
        body: JSON.stringify({
          user_id: "operator",
          title: nextNumber === 1 ? "New Idea" : `Idea ${nextNumber}`,
        }),
      });
      setSessionDetails((current) => ({ ...current, [detail.session.id]: detail }));
      setSessions((current) => [detail.session, ...current]);
      setOpenSessionIds((current) => [detail.session.id, ...current.filter((id) => id !== detail.session.id)]);
      setActiveTab(detail.session.id);
      setMessageDraft("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to create ideation tab");
    } finally {
      setIsBusy(false);
    }
  }, [sessions.length]);

  const activateSavedIndexes = useCallback(async () => {
    setActiveTab(SAVED_INDEXES_TAB);
    if (selectedIndexId) {
      const detail = await apiRequest<IndexDetail>(`/indexes/${selectedIndexId}`);
      setIndexDetail(detail);
    }
  }, [selectedIndexId]);

  const sendMessage = useCallback(async () => {
    if (!activeSessionId || !messageDraft.trim()) {
      return;
    }
    setIsBusy(true);
    setError(null);
    try {
      const detail = await apiRequest<IdeationSessionDetailResponse>(
        `/ideation/sessions/${activeSessionId}/messages`,
        {
          method: "POST",
          body: JSON.stringify({ content: messageDraft.trim() }),
        },
      );
      setSessionDetails((current) => ({ ...current, [activeSessionId]: detail }));
      setSessions((current) => {
        const next = current.filter((item) => item.id !== detail.session.id);
        next.unshift(detail.session);
        return next;
      });
      setMessageDraft("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to send message");
    } finally {
      setIsBusy(false);
    }
  }, [activeSessionId, messageDraft]);

  const convertSession = useCallback(async () => {
    if (!activeSessionId) {
      return;
    }
    setIsBusy(true);
    setError(null);
    try {
      const converted = await apiRequest<ConvertIdeationSessionResponse>(
        `/ideation/sessions/${activeSessionId}/convert-to-index`,
        { method: "POST" },
      );
      setSessionDetails((current) => ({
        ...current,
        [activeSessionId]: {
          ...(current[activeSessionId] ?? { messages: [] }),
          session: converted.session,
          messages: current[activeSessionId]?.messages ?? [],
        },
      }));
      setSessions((current) => {
        const next = current.filter((item) => item.id !== converted.session.id);
        next.unshift(converted.session);
        return next;
      });
      setActiveTab(SAVED_INDEXES_TAB);
      await refreshIndexes(converted.index.id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to convert session");
    } finally {
      setIsBusy(false);
    }
  }, [activeSessionId, refreshIndexes]);

  const openIndexAsIdea = useCallback(async (indexId: string) => {
    setIsBusy(true);
    setError(null);
    try {
      const detail = await apiRequest<IdeationSessionDetailResponse>(`/indexes/${indexId}/open-ideation`, {
        method: "POST",
      });
      setSessionDetails((current) => ({ ...current, [detail.session.id]: detail }));
      setSessions((current) => [detail.session, ...current.filter((item) => item.id !== detail.session.id)]);
      setOpenSessionIds((current) => [detail.session.id, ...current.filter((id) => id !== detail.session.id)]);
      setActiveTab(detail.session.id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to open ideation tab");
    } finally {
      setIsBusy(false);
    }
  }, []);

  const selectIndex = useCallback(async (indexId: string) => {
    setSelectedIndexId(indexId);
    setError(null);
    try {
      const detail = await apiRequest<IndexDetail>(`/indexes/${indexId}`);
      setIndexDetail(detail);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to load index");
    }
  }, []);

  const refreshModelRegistry = useCallback(async () => {
    setIsBusy(true);
    setError(null);
    try {
      const response = await apiRequest<ModelRefreshResponse>("/models/refresh", { method: "POST" });
      setCurrentModels(response.current);
      await refreshModels();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to refresh model registry");
    } finally {
      setIsBusy(false);
    }
  }, [refreshModels]);

  const approveModelProposal = useCallback(async (proposalId: string) => {
    setIsBusy(true);
    setError(null);
    try {
      const current = await apiRequest<CurrentModelSetResponse>(`/models/proposals/${proposalId}/approve`, {
        method: "POST",
      });
      setCurrentModels(current.model_set);
      await refreshModels();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to approve model proposal");
    } finally {
      setIsBusy(false);
    }
  }, [refreshModels]);

  const resetLocalRuntime = useCallback(async () => {
    setIsBusy(true);
    setError(null);
    try {
      await apiRequest<DevResetResponse>("/dev/reset", { method: "POST" });
      setSessionDetails({});
      setOpenSessionIds([]);
      setActiveTab(SAVED_INDEXES_TAB);
      setSelectedIndexId(null);
      setIndexDetail(null);
      await refreshAll();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to clear local runtime data");
    } finally {
      setIsBusy(false);
    }
  }, [refreshAll]);

  return (
    <main className="workbookApp" data-testid="workbook-app">
      <header className="topbar" data-testid="topbar">
        <div className="brandBlock">
          <p className="eyebrow">Agentic Indexing</p>
          <h1>Workbook for custom index design</h1>
          <p className="lede">
            Chat drives the specification on the right. The workbook tiles on the left fill in as
            the thesis, vehicles, benchmarks, and approval rules become concrete.
          </p>
        </div>

        <div className="headerControls">
          <button
            className="headerButton"
            data-testid="new-idea-button"
            onClick={createNewIdeaTab}
            disabled={isBusy}
            type="button"
          >
            + New Idea
          </button>
          <button
            className="modelBadge"
            data-testid="model-badge-button"
            onClick={() => setShowModelAdmin((current) => !current)}
            type="button"
          >
            <span>Model Set</span>
            <strong>
              {currentModels
                ? `${currentModels.openai_model.label} / ${currentModels.anthropic_model.label} / ${currentModels.google_model.label}`
                : "Loading..."}
            </strong>
            <em>{modelProposals.length} pending</em>
          </button>
        </div>
      </header>

      {showModelAdmin ? (
        <section className="adminPanel" data-testid="model-admin-panel">
          <div>
            <p className="panelLabel">Current approved trio</p>
            {currentModels ? (
              <div className="modelGrid">
                {[currentModels.openai_model, currentModels.anthropic_model, currentModels.google_model].map((item) => (
                  <article key={item.id} className="modelCard">
                    <span className="pill pill-neutral">{item.provider}</span>
                    <strong>{item.label}</strong>
                    <a href={item.official_doc_url} rel="noreferrer" target="_blank">
                      official docs
                    </a>
                  </article>
                ))}
              </div>
            ) : null}
          </div>
          <div className="adminActions">
            <button
              className="headerButton secondary"
              data-testid="refresh-model-registry-button"
              onClick={refreshModelRegistry}
              type="button"
            >
              Refresh registry
            </button>
            <button
              className="headerButton secondary"
              data-testid="clear-runtime-button"
              onClick={resetLocalRuntime}
              type="button"
            >
              Clear local runtime data
            </button>
          </div>
          {modelProposals.length ? (
            <div className="proposalList">
              {modelProposals.map((proposal) => (
                <article key={proposal.id} className="proposalCard">
                  <div>
                    <p className="panelLabel">Pending proposal</p>
                    <strong>
                      {proposal.proposed_set.openai_model.label} / {proposal.proposed_set.anthropic_model.label} / {" "}
                      {proposal.proposed_set.google_model.label}
                    </strong>
                    <p>{proposal.rationale}</p>
                  </div>
                  <button
                    className="headerButton"
                    data-testid={`approve-model-proposal-${proposal.id}`}
                    onClick={() => void approveModelProposal(proposal.id)}
                    type="button"
                  >
                    Approve switch
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <p className="microcopy">No pending model-set proposals.</p>
          )}
        </section>
      ) : null}

      <section className="tabbar" data-testid="workbook-tabbar">
        <button
          className={`tab ${activeTab === SAVED_INDEXES_TAB ? "active" : ""}`}
          data-testid="saved-indexes-tab"
          onClick={() => void activateSavedIndexes()}
          type="button"
        >
          Saved Indexes
        </button>
        {openSessions.map((session) => (
          <button
            key={session.id}
            className={`tab ${activeTab === session.id ? "active" : ""}`}
            data-testid={`ideation-tab-${session.id}`}
            onClick={() => setActiveTab(session.id)}
            type="button"
          >
            {shortTabTitle(session.title)}
          </button>
        ))}
      </section>

      {error ? <div className="errorBanner" data-testid="error-banner">{error}</div> : null}

      {activeTab === SAVED_INDEXES_TAB ? (
        <section className="savedIndexesLayout" data-testid="saved-indexes-layout">
          <aside className="savedRail sheetPanel" data-testid="saved-indexes-rail">
            <div className="sectionHeader compact">
              <div>
                <p className="panelLabel">Saved indexes</p>
                <h2>Library</h2>
              </div>
              <button
                className="headerButton secondary"
                data-testid="new-ideation-tab-button"
                onClick={createNewIdeaTab}
                type="button"
              >
                New ideation tab
              </button>
            </div>
            <div className="indexList" data-testid="saved-indexes-list">
              {indexes.length === 0 ? <p className="emptyState">No saved indexes yet.</p> : null}
              {indexes.map((index) => (
                <button
                  key={index.id}
                  className={`indexCard ${selectedIndexId === index.id ? "selected" : ""}`}
                  data-testid={`saved-index-card-${index.id}`}
                  onClick={() => void selectIndex(index.id)}
                  type="button"
                >
                  <strong>{index.name}</strong>
                  <span>{index.holdings_count} holdings</span>
                  <span>{formatPercent(index.latest_cagr)} 1Y</span>
                </button>
              ))}
            </div>
          </aside>

          <section className="savedCanvas sheetPanel" data-testid="saved-index-detail">
            {indexDetail ? (
              <>
                <div className="sectionHeader">
                  <div>
                    <p className="panelLabel">Selected index</p>
                    <h2>{indexDetail.name}</h2>
                  </div>
                  <div className="statusStack">
                    <span className={`pill pill-${indexDetail.status}`}>{indexDetail.status}</span>
                    <span className="microcopy">{formatLabel(indexDetail.rebalance_cadence)}</span>
                  </div>
                </div>

                <div className="summaryGrid">
                  <article className="summaryCard">
                    <p className="panelLabel">Thesis</p>
                    <p>{indexDetail.thesis_summary}</p>
                  </article>
                  <article className="summaryCard">
                    <p className="panelLabel">Approval state</p>
                    <p>{indexDetail.approval_status ?? "No active order bundle"}</p>
                  </article>
                  <article className="summaryCard full">
                    <p className="panelLabel">Performance windows</p>
                    <div className="timeframeGrid">
                      {indexDetail.performance.map((row) => (
                        <div key={row.timeframe} className="metricCell">
                          <span>{row.timeframe}</span>
                          <strong>{formatPercent(row.strategy_return)}</strong>
                        </div>
                      ))}
                    </div>
                  </article>
                </div>

                <div className="detailGrid">
                  <article className="summaryCard">
                    <p className="panelLabel">Holdings</p>
                    <div className="holdingsList">
                      {indexDetail.holdings.map((holding) => (
                        <div key={holding.symbol} className="holdingRow">
                          <div>
                            <strong>{holding.symbol}</strong>
                            <span>{holding.name}</span>
                          </div>
                          <span>{formatPercent(holding.weight)}</span>
                        </div>
                      ))}
                    </div>
                  </article>

                  <article className="summaryCard">
                    <p className="panelLabel">Benchmark summary</p>
                    <div className="benchmarkList">
                      {indexDetail.performance.map((row) => (
                        <div key={row.timeframe} className="benchmarkBlock">
                          <strong>{row.timeframe}</strong>
                          {performanceRow(row).map((item) => (
                            <div key={`${row.timeframe}-${item.name}`} className="benchmarkRow">
                              <span>{formatLabel(item.name)}</span>
                              <span>{formatPercent(item.value)}</span>
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  </article>
                </div>

                <div className="sectionHeader compact footerAction">
                  <div>
                    <p className="panelLabel">Next step</p>
                    <p className="microcopy">Open a fresh ideation workbook from this saved index.</p>
                  </div>
                  <button
                    className="headerButton"
                    data-testid="open-new-ideation-from-index-button"
                    onClick={() => void openIndexAsIdea(indexDetail.id)}
                    type="button"
                  >
                    Open new ideation tab
                  </button>
                </div>
              </>
            ) : (
              <div className="emptyCanvas">
                <p className="panelLabel">Saved indexes</p>
                <h2>No saved index selected</h2>
                <p>Select an index from the left or open a new ideation tab.</p>
              </div>
            )}
          </section>
        </section>
      ) : (
        <section className="ideationLayout" data-testid="ideation-layout">
          <section className="sheetPanel workbookCanvas" data-testid="workbook-canvas">
            <div className="sectionHeader">
              <div>
                <p className="panelLabel">Ideation workbook</p>
                <h2>{activeSession?.title ?? "Loading..."}</h2>
              </div>
              <div className="statusStack">
                <span className={`pill pill-${activeSession?.status ?? "neutral"}`}>
                  {activeSession ? sessionStatusLabel(activeSession.status) : "loading"}
                </span>
                <button
                  className="headerButton secondary"
                  data-testid="convert-session-button"
                  onClick={convertSession}
                  type="button"
                >
                  Convert to saved index
                </button>
              </div>
            </div>

            <div className="sessionMeta">
              <span>{activeSession?.raw_thesis || "Start the conversation to define the thesis."}</span>
              <span>{councilCount(activeSession?.council_summary ?? null)}</span>
            </div>

            <div className="tileGrid" data-testid="decision-tile-grid">
              {activeSession?.decision_tiles.map((tile) => (
                <article
                  key={tile.key}
                  className={`tileCard tile-${tile.status}`}
                  data-testid={`decision-tile-${tile.key}`}
                >
                  <div className="tileHeader">
                    <p className="panelLabel">{tile.title}</p>
                    <span className={`pill pill-${tile.status}`}>{formatLabel(tile.status)}</span>
                  </div>
                  <p>{tile.summary}</p>
                  {tile.bullets.length ? (
                    <ul className="bulletList compact">
                      {tile.bullets.map((bullet) => (
                        <li key={bullet}>{bullet}</li>
                      ))}
                    </ul>
                  ) : null}
                </article>
              ))}
            </div>

            <div className="councilPanel" data-testid="council-panel">
              <div className="sectionHeader compact">
                <div>
                  <p className="panelLabel">Council summary</p>
                  <p>{activeSession?.council_summary?.headline ?? "Waiting for your first message."}</p>
                </div>
                <button
                  className="headerButton secondary"
                  data-testid="toggle-council-details-button"
                  onClick={() =>
                    setExpandedCouncilTab((current) => (current === activeSessionId ? null : activeSessionId))
                  }
                  type="button"
                >
                  {expandedCouncilTab === activeSessionId ? "Hide details" : "Show details"}
                </button>
              </div>
              {expandedCouncilTab === activeSessionId && activeSession?.council_summary ? (
                <div className="auditList">
                  {activeSession.council_summary.reports.map((report) => (
                    <article key={`${report.model}-${report.content_hash}`} className="auditCard">
                      <div className="auditHeader">
                        <strong>{report.model}</strong>
                        <span className={`pill pill-${report.verdict === "pass" ? "resolved" : "blocked_by_council"}`}>
                          {report.verdict}
                        </span>
                      </div>
                      <p>{report.stage}</p>
                      <ul className="bulletList compact">
                        {report.reasons.map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                    </article>
                  ))}
                </div>
              ) : null}
            </div>
          </section>

          <aside className="chatRail sheetPanel" data-testid="chat-rail">
            <div className="sectionHeader compact">
              <div>
                <p className="panelLabel">Conversation</p>
                <h3>Chat-driven ideation</h3>
              </div>
              <span className="microcopy">Pinned right rail</span>
            </div>

            <div className="messageList" data-testid="message-list">
              {activeMessages.map((message: IdeationMessage) => (
                <article key={message.id} className={`messageBubble role-${message.role}`}>
                  <span className="messageRole">{message.role}</span>
                  <p>{message.content}</p>
                </article>
              ))}
            </div>

            <form
              className="composer"
              data-testid="message-composer"
              onSubmit={(event) => {
                event.preventDefault();
                void sendMessage();
              }}
            >
              <textarea
                data-testid="message-input"
                value={messageDraft}
                onChange={(event) => setMessageDraft(event.target.value)}
                placeholder="Describe the thesis, constraints, benchmarks, weighting, or rebalance logic."
                rows={6}
              />
              <div className="composerActions">
                <span className="microcopy">The workbook updates after each message.</span>
                <button
                  className="headerButton"
                  data-testid="send-message-button"
                  disabled={isBusy || !messageDraft.trim()}
                  type="submit"
                >
                  Send
                </button>
              </div>
            </form>
          </aside>
        </section>
      )}
    </main>
  );
}
