import crypto from "node:crypto";

type ProxyEvent = {
  timestamp: string;
  profile: string;
  proxyRequestId: string;
  targetUrl: string;
  method: string;
  status: number | null;
  backendRequestId: string | null;
  testRunId: string | null;
  error: string | null;
};

type RuntimeStatus = {
  service: "agentic-indexing-web";
  profile: string;
  apiOrigin: string;
  runtimeBuildId: string;
  backendHealthy: boolean;
  backendStatusCode: number | null;
  backendRequestId: string | null;
  configurationWarning: string | null;
  latestProxyError: ProxyEvent | null;
  recentProxyEventCount: number;
};

declare global {
  // eslint-disable-next-line no-var
  var __AGENTIC_PROXY_EVENTS__: ProxyEvent[] | undefined;
}

function proxyStore(): ProxyEvent[] {
  if (!globalThis.__AGENTIC_PROXY_EVENTS__) {
    globalThis.__AGENTIC_PROXY_EVENTS__ = [];
  }
  return globalThis.__AGENTIC_PROXY_EVENTS__;
}

export function runtimeProfile(): string {
  return process.env.AGENTIC_PROFILE ?? "manual";
}

export function runtimeBuildId(): string {
  return process.env.AGENTIC_RUNTIME_BUILD_ID ?? "dev";
}

export function apiOrigin(): string {
  return process.env.AGENTIC_API_ORIGIN ?? "http://127.0.0.1:8000";
}

export function configurationWarning(): string | null {
  const profile = runtimeProfile();
  const origin = apiOrigin();
  if (profile !== "verification" && origin.includes(":8100")) {
    return "Manual runtime is pointed at the verification API port 8100.";
  }
  return null;
}

export function proxyRequestId(): string {
  return `proxy-${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;
}

export function recordProxyEvent(event: ProxyEvent): void {
  const store = proxyStore();
  store.push(event);
  if (store.length > 200) {
    store.splice(0, store.length - 200);
  }
  if ((process.env.AGENTIC_JSON_LOGS ?? "1") === "1") {
    // Keep proxy logs machine-readable for agent triage.
    // eslint-disable-next-line no-console
    console.log(JSON.stringify({ type: "web_proxy_event", ...event }));
  }
}

export function latestProxyError(): ProxyEvent | null {
  const store = proxyStore();
  for (let index = store.length - 1; index >= 0; index -= 1) {
    const item = store[index];
    if (item.error || (item.status !== null && item.status >= 400)) {
      return item;
    }
  }
  return null;
}

export async function collectRuntimeStatus(): Promise<RuntimeStatus> {
  const origin = apiOrigin();
  const warning = configurationWarning();

  let backendHealthy = false;
  let backendStatusCode: number | null = null;
  let backendRequestId: string | null = null;

  try {
    const response = await fetch(`${origin}/runtime/status`, {
      cache: "no-store",
      headers: {
        "X-Proxy-Request-Id": proxyRequestId(),
      },
    });
    backendStatusCode = response.status;
    backendRequestId = response.headers.get("X-Request-Id");
    backendHealthy = response.ok;
  } catch {
    backendHealthy = false;
  }

  return {
    service: "agentic-indexing-web",
    profile: runtimeProfile(),
    apiOrigin: origin,
    runtimeBuildId: runtimeBuildId(),
    backendHealthy,
    backendStatusCode,
    backendRequestId,
    configurationWarning: warning,
    latestProxyError: latestProxyError(),
    recentProxyEventCount: proxyStore().length,
  };
}
