import { NextResponse } from "next/server";

import { getSupabaseAdminClient, hasSupabaseAdminEnv } from "../../../lib/supabase/admin";

export const dynamic = "force-dynamic";

export async function GET() {
  const timestamp = new Date().toISOString();
  const release = process.env.VERCEL_GIT_COMMIT_SHA ?? process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA ?? null;
  const sentryEnabled = Boolean(process.env.SENTRY_DSN ?? process.env.NEXT_PUBLIC_SENTRY_DSN);
  const supabaseConfigured = hasSupabaseAdminEnv();

  const checks = {
    application: { ok: true, status: "ok" as const },
    database: {
      ok: false,
      status: "not_configured" as "ok" | "failed" | "not_configured",
      detail: "Supabase admin environment variables are missing.",
    },
    sentry: {
      ok: sentryEnabled,
      status: (sentryEnabled ? "ok" : "disabled") as "ok" | "disabled",
    },
  };

  if (supabaseConfigured) {
    const client = getSupabaseAdminClient();
    const { error } = await client!.from("inquiries").select("id", { count: "exact", head: true }).limit(1);

    if (error) {
      checks.database = {
        ok: false,
        status: "failed",
        detail: error.message,
      };
    } else {
      checks.database = {
        ok: true,
        status: "ok",
        detail: "Supabase reachable.",
      };
    }
  }

  const ok = checks.application.ok && checks.database.ok;
  const status = ok ? "ok" : "degraded";

  return NextResponse.json(
    {
      ok,
      status,
      timestamp,
      release,
      checks,
    },
    {
      status: ok ? 200 : 503,
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
    },
  );
}
