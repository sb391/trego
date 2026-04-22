import "server-only";

import { getSupabaseAdminClient } from "../supabase/admin";
import { isAllowedAdminEmail } from "../supabase/config";
import { getSupabaseServerClient } from "../supabase/server";

export type AdminSessionUser = {
  id: string;
  email: string;
  fullName: string | null;
};

async function syncAdminUser(user: AdminSessionUser) {
  const adminClient = getSupabaseAdminClient();
  if (!adminClient) {
    return;
  }

  await adminClient.from("admin_users").upsert(
    {
      auth_user_id: user.id,
      email: user.email,
      full_name: user.fullName,
      is_active: true,
      role: "admin",
    },
    {
      onConflict: "email",
      ignoreDuplicates: false,
    },
  );
}

export async function getAuthenticatedAdmin(): Promise<AdminSessionUser | null> {
  const client = await getSupabaseServerClient();
  if (!client) {
    return null;
  }

  const {
    data: { user },
  } = await client.auth.getUser();

  if (!user?.email || !isAllowedAdminEmail(user.email)) {
    return null;
  }

  const adminUser = {
    id: user.id,
    email: user.email,
    fullName: user.user_metadata?.full_name ?? user.user_metadata?.name ?? null,
  };

  await syncAdminUser(adminUser);
  return adminUser;
}
