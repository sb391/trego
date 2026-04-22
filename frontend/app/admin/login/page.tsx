import Link from "next/link";

import { AdminLoginForm } from "../../../components/admin/AdminLoginForm";
import { hasSupabaseBrowserEnv } from "../../../lib/supabase/config";

type SearchParamsValue = string | string[] | undefined;

export default async function AdminLoginPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, SearchParamsValue>>;
}) {
  const params = searchParams ? await searchParams : {};
  const nextPath = typeof params.next === "string" ? params.next : "/admin";
  const supabaseReady = hasSupabaseBrowserEnv();

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f7f3ec_0%,#fbf8f4_100%)] px-4 py-10 text-[#111a2e] sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[80vh] max-w-5xl items-center">
        <div className="grid w-full gap-8 lg:grid-cols-[0.95fr_1.05fr]">
          <section className="rounded-[1.8rem] border border-[#ece2e6] bg-white px-6 py-7 shadow-[0_18px_40px_rgba(10,37,64,0.05)] sm:px-8 sm:py-8">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-[#b86140]">TreGo admin access</p>
            <h1 className="mt-3 text-[1.7rem] font-extrabold tracking-[-0.05em] text-[#2d1870] sm:text-[2.2rem]">
              Sign in to review inquiries and company intelligence.
            </h1>
            <p className="mt-4 text-[0.98rem] leading-7 text-[#69798b]">
              This console is intended for internal operating use: inbound inquiries, agri intelligence lookup, and
              downloadable joined dumps for analyst follow-through.
            </p>

            <div className="mt-8 space-y-4 rounded-[1.2rem] border border-[#efe5e2] bg-[#fcfaf7] px-5 py-5">
              <div>
                <div className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#90a2b6]">Redirect after login</div>
                <div className="mt-2 text-[0.96rem] text-[#2a3550]">{nextPath}</div>
              </div>
              <div>
                <div className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#90a2b6]">Auth mode</div>
                <div className="mt-2 text-[0.96rem] text-[#2a3550]">
                  {supabaseReady ? "Supabase password sign-in" : "Supabase browser auth not configured yet"}
                </div>
              </div>
              <Link
                href="/"
                className="interactive-press inline-flex items-center justify-center rounded-full border border-[#e5d9d7] bg-white px-4 py-2 text-[0.75rem] font-semibold uppercase tracking-[0.12em] text-[#6f6176]"
              >
                Back to site
              </Link>
            </div>
          </section>

          <section className="rounded-[1.8rem] border border-[#ece2e6] bg-white px-6 py-7 shadow-[0_18px_40px_rgba(10,37,64,0.05)] sm:px-8 sm:py-8">
            <div className="max-w-md">
              <div className="text-[0.74rem] font-semibold uppercase tracking-[0.2em] text-[#b86140]">Admin login</div>
              <h2 className="mt-3 text-[1.45rem] font-extrabold tracking-[-0.04em] text-[#2d1870]">
                Use your approved TreGo admin credentials.
              </h2>
              <p className="mt-3 text-[0.95rem] leading-7 text-[#69798b]">
                We recommend creating a dedicated admin user in Supabase Auth and allowlisting the email before
                turning this on publicly.
              </p>
            </div>

            <div className="mt-8">
              <AdminLoginForm />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
