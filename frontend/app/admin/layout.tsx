import Link from "next/link";
import type { ReactNode } from "react";

import { AdminSignOutButton } from "../../components/admin/AdminSignOutButton";
import { getAuthenticatedAdmin } from "../../lib/admin/auth";
import { hasSupabaseAdminEnv } from "../../lib/supabase/admin";

const adminLinks = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/inquiries", label: "Inquiries" },
  { href: "/admin/agri-companies", label: "Agri Intelligence" },
  { href: "/admin/exports", label: "Exports" },
  { href: "/admin/setup", label: "Setup" },
] as const;

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const supabaseReady = hasSupabaseAdminEnv();
  const adminUser = await getAuthenticatedAdmin();

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f7f3ec_0%,#fbf8f4_100%)] text-[#111a2e]">
      <header className="border-b border-[#ece2e6] bg-white/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 sm:px-8 lg:px-12">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-[0.7rem] font-semibold uppercase tracking-[0.28em] text-[#b86140]">TreGo admin</p>
              <h1 className="mt-2 text-[1.6rem] font-extrabold tracking-[-0.05em] text-[#2d1870]">
                Production data console
              </h1>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Link
                href="/"
                className="interactive-press inline-flex items-center justify-center rounded-full border border-[#e6d9da] bg-white px-4 py-2 text-[0.75rem] font-semibold uppercase tracking-[0.12em] text-[#6f6176]"
              >
                Back to site
              </Link>
              {adminUser ? (
                <div className="rounded-full border border-[#ece2e6] bg-[#fcfaf7] px-4 py-2 text-[0.76rem] font-semibold uppercase tracking-[0.12em] text-[#5f6f82]">
                  {adminUser.email}
                </div>
              ) : null}
              {adminUser ? <AdminSignOutButton /> : null}
              <div
                className={[
                  "rounded-full border px-4 py-2 text-[0.72rem] font-semibold uppercase tracking-[0.14em]",
                  supabaseReady
                    ? "border-[#cfe4d1] bg-[#eff8f1] text-[#2f7d3a]"
                    : "border-[#eadbd4] bg-[#fff8f4] text-[#a65f41]",
                ].join(" ")}
              >
                {supabaseReady ? "Supabase connected" : "Seed / local mode"}
              </div>
            </div>
          </div>

          <nav className="flex flex-wrap gap-2">
            {adminLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="interactive-press rounded-full border border-[#eadfe0] bg-[#fcfaf7] px-4 py-2 text-[0.76rem] font-semibold uppercase tracking-[0.12em] text-[#5f6f82] transition hover:border-[#d8c8cd] hover:text-[#2d1870]"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      {!supabaseReady ? (
        <div className="border-b border-[#f1e3df] bg-[#fff8f4]">
          <div className="mx-auto max-w-7xl px-4 py-3 text-[0.9rem] text-[#805640] sm:px-8 lg:px-12">
            Supabase is not configured yet, so inquiries fall back to local dev storage and agri intelligence reads
            from the consolidated seed generated from the current export.
          </div>
        </div>
      ) : null}

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-8 lg:px-12 lg:py-10">{children}</main>
    </div>
  );
}
