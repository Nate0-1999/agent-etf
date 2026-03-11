import { NextResponse } from "next/server";

import { collectRuntimeStatus } from "../../../../lib/server/runtime";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const status = await collectRuntimeStatus();
  return NextResponse.json(status, {
    headers: {
      "X-Agentic-Profile": status.profile,
      "X-Agentic-Runtime-Build-Id": status.runtimeBuildId,
    },
  });
}
