export type VerificationApiEvent = {
  timestamp: string;
  path: string;
  method: string;
  status: number;
  requestId: string | null;
  proxyRequestId?: string | null;
  backendRequestId?: string | null;
  requestUrl?: string | null;
  requestBody?: string | null;
  testRunId: string | null;
};

export type VerificationState = {
  route: string;
  activeTab: string;
  openTabs: string[];
  savedIndexCount: number;
  selectedIndexName: string | null;
  showModelAdmin: boolean;
  pendingModelProposalCount: number;
  error: string | null;
  isBusy: boolean;
  runtime: {
    profile: string;
    apiOrigin: string;
    runtimeBuildId: string;
    backendHealthy: boolean;
    configurationWarning: string | null;
    latestProxyError: string | null;
  } | null;
  session: {
    title: string | null;
    status: string | null;
    messageCount: number;
    councilHeadline: string | null;
    tileStatuses: Record<string, string>;
  } | null;
};

declare global {
  interface Window {
    __AGENTIC_INDEXING_TEST_RUN_ID__?: string;
    __AGENTIC_INDEXING_TEST_STATE__?: VerificationState;
    __AGENTIC_INDEXING_API_LOG__?: VerificationApiEvent[];
    __AGENTIC_INDEXING_LAST_RENDER_AT__?: number;
  }
}

export function getTestRunId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.__AGENTIC_INDEXING_TEST_RUN_ID__ ?? null;
}

export function appendApiEvent(event: VerificationApiEvent): void {
  if (typeof window === "undefined") {
    return;
  }
  const current = window.__AGENTIC_INDEXING_API_LOG__ ?? [];
  current.push(event);
  window.__AGENTIC_INDEXING_API_LOG__ = current.slice(-100);
}

export function publishVerificationState(state: VerificationState): void {
  if (typeof window === "undefined") {
    return;
  }
  window.__AGENTIC_INDEXING_TEST_STATE__ = state;
  window.__AGENTIC_INDEXING_LAST_RENDER_AT__ = Date.now();
}
