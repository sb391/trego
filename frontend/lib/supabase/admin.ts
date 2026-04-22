import "server-only";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import { getSupabaseUrl } from "./config";

let cachedAdminClient: SupabaseClient | null | undefined;

export function hasSupabaseAdminEnv(): boolean {
  return Boolean(getSupabaseUrl() && process.env.SUPABASE_SERVICE_ROLE_KEY);
}

export function getSupabaseAdminClient(): SupabaseClient | null {
  if (!hasSupabaseAdminEnv()) {
    return null;
  }

  if (cachedAdminClient !== undefined) {
    return cachedAdminClient;
  }

  cachedAdminClient = createClient(
    getSupabaseUrl() as string,
    process.env.SUPABASE_SERVICE_ROLE_KEY as string,
    {
      auth: {
        autoRefreshToken: false,
        persistSession: false,
      },
    },
  );

  return cachedAdminClient;
}
