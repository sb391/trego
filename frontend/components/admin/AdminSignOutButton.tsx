"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { getSupabaseBrowserClient } from "../../lib/supabase/browser";

export function AdminSignOutButton() {
  const router = useRouter();
  const [isWorking, setIsWorking] = useState(false);

  async function handleSignOut() {
    const supabase = getSupabaseBrowserClient();
    setIsWorking(true);

    if (supabase) {
      await supabase.auth.signOut();
    }

    router.replace("/admin/login");
    router.refresh();
  }

  return (
    <button
      type="button"
      onClick={handleSignOut}
      disabled={isWorking}
      className="interactive-press inline-flex items-center justify-center rounded-full border border-[#e6d9da] bg-white px-4 py-2 text-[0.75rem] font-semibold uppercase tracking-[0.12em] text-[#6f6176] disabled:cursor-not-allowed disabled:opacity-70"
    >
      {isWorking ? "Signing out..." : "Sign out"}
    </button>
  );
}
