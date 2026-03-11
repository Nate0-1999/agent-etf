import { type NextRequest, NextResponse } from "next/server";

import {
  apiOrigin,
  proxyRequestId,
  recordProxyEvent,
  runtimeBuildId,
  runtimeProfile,
} from "../../../lib/server/runtime";

export const dynamic = "force-dynamic";

function buildTargetUrl(request: NextRequest, path: string[]): string {
  const target = new URL(`${apiOrigin()}/${path.join("/")}`);
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.append(key, value);
  });
  return target.toString();
}

function copyHeaders(request: NextRequest, proxyId: string): Headers {
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (["host", "connection", "content-length"].includes(lower)) {
      return;
    }
    headers.set(key, value);
  });
  headers.set("X-Proxy-Request-Id", proxyId);
  headers.set("X-Agentic-Profile", runtimeProfile());
  headers.set("X-Agentic-Runtime-Build-Id", runtimeBuildId());
  headers.set("X-Forwarded-By", "agentic-indexing-next-proxy");
  return headers;
}

async function proxyRequest(request: NextRequest, path: string[]): Promise<NextResponse> {
  const proxyId = proxyRequestId();
  const targetUrl = buildTargetUrl(request, path);
  const method = request.method.toUpperCase();
  const testRunId = request.headers.get("X-Test-Run-Id");
  const body =
    method === "GET" || method === "HEAD"
      ? undefined
      : await request.arrayBuffer();

  try {
    const upstream = await fetch(targetUrl, {
      method,
      headers: copyHeaders(request, proxyId),
      body,
      cache: "no-store",
      redirect: "manual",
    });
    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.set("X-Proxy-Request-Id", proxyId);
    responseHeaders.set("X-Backend-Request-Id", upstream.headers.get("X-Request-Id") ?? "");
    responseHeaders.set("X-Agentic-Profile", runtimeProfile());
    responseHeaders.set("X-Agentic-Runtime-Build-Id", runtimeBuildId());
    recordProxyEvent({
      timestamp: new Date().toISOString(),
      profile: runtimeProfile(),
      proxyRequestId: proxyId,
      targetUrl,
      method,
      status: upstream.status,
      backendRequestId: upstream.headers.get("X-Request-Id"),
      testRunId,
      error: null,
    });
    return new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown proxy failure";
    recordProxyEvent({
      timestamp: new Date().toISOString(),
      profile: runtimeProfile(),
      proxyRequestId: proxyId,
      targetUrl,
      method,
      status: null,
      backendRequestId: null,
      testRunId,
      error: message,
    });
    return new NextResponse(
      `Proxy request failed while contacting ${targetUrl}: ${message}`,
      {
        status: 502,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "X-Proxy-Request-Id": proxyId,
          "X-Agentic-Profile": runtimeProfile(),
          "X-Agentic-Runtime-Build-Id": runtimeBuildId(),
        },
      },
    );
  }
}

export async function GET(
  request: NextRequest,
  context: { params: { path: string[] } },
): Promise<NextResponse> {
  return proxyRequest(request, context.params.path);
}

export async function POST(
  request: NextRequest,
  context: { params: { path: string[] } },
): Promise<NextResponse> {
  return proxyRequest(request, context.params.path);
}

export async function OPTIONS(
  request: NextRequest,
  context: { params: { path: string[] } },
): Promise<NextResponse> {
  return proxyRequest(request, context.params.path);
}
