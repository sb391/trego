import { getAllowedAdminEmails, hasSupabaseBrowserEnv } from "../../../lib/supabase/config";
import { hasSupabaseAdminEnv } from "../../../lib/supabase/admin";

const migrationFiles = [
  "supabase/migrations/20260421_trego_foundation.sql",
  "supabase/migrations/20260421_trego_admin_workflow.sql",
] as const;

const onboardingSteps = [
  {
    title: "Configure environment variables",
    body:
      "Add the same Supabase project values in both local .env.local and the Vercel project settings so the website, admin auth, and export logging all point to one backend.",
    commands: [
      "cp .env.example .env.local",
      "NEXT_PUBLIC_SUPABASE_URL=...",
      "NEXT_PUBLIC_SUPABASE_ANON_KEY=...",
      "SUPABASE_SERVICE_ROLE_KEY=...",
      "ADMIN_ALLOWED_EMAILS=you@tregocapital.com,ops@tregocapital.com",
    ],
  },
  {
    title: "Run the Supabase migrations",
    body:
      "Execute both SQL files in the Supabase SQL editor, in order, so the admin workflow fields and export-job metadata exist before inquiries or downloads hit production.",
    commands: migrationFiles,
  },
  {
    title: "Create admin users in Supabase Auth",
    body:
      "Open Authentication → Users in Supabase, create or invite the internal admin emails, and make sure each email is listed in ADMIN_ALLOWED_EMAILS so the middleware allows access.",
    commands: ["Supabase Dashboard → Authentication → Users → Add user / Invite user"],
  },
  {
    title: "Seed the agri master",
    body:
      "Run the resettable seed from the frontend workspace. This clears prior agri intelligence rows, loads the normalized master, and links everything to a fresh import run.",
    commands: ["npm run seed:agri:reset"],
  },
  {
    title: "Validate the full admin flow",
    body:
      "Confirm the site can submit an inquiry, the inquiry lands in /admin/inquiries, status updates save, and all three admin exports download cleanly.",
    commands: ["npm run build", "npm run dev"],
  },
] as const;

export default function AdminSetupPage() {
  const browserReady = hasSupabaseBrowserEnv();
  const adminReady = hasSupabaseAdminEnv();
  const allowedEmails = getAllowedAdminEmails();

  return (
    <div className="space-y-6">
      <section className="rounded-[1.6rem] border border-[#ece2e6] bg-white px-6 py-6 shadow-[0_16px_34px_rgba(10,37,64,0.04)]">
        <p className="text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-[#b86140]">Setup</p>
        <h2 className="mt-2 text-[1.55rem] font-extrabold tracking-[-0.05em] text-[#2d1870]">
          Exact onboarding steps for this TreGo admin project
        </h2>
        <p className="mt-3 max-w-3xl text-[0.95rem] leading-7 text-[#69798b]">
          This page is the final-mile checklist for your current stack: Vercel frontend, Supabase auth/database, and
          the agri intelligence master already generated in this repository.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <StatusCard
          label="Browser auth env"
          value={browserReady ? "Ready" : "Missing"}
          tone={browserReady ? "ready" : "missing"}
          detail="NEXT_PUBLIC_SUPABASE_URL + ANON key"
        />
        <StatusCard
          label="Admin service env"
          value={adminReady ? "Ready" : "Missing"}
          tone={adminReady ? "ready" : "missing"}
          detail="SUPABASE_SERVICE_ROLE_KEY"
        />
        <StatusCard
          label="Admin allowlist"
          value={allowedEmails.length > 0 ? String(allowedEmails.length) : "Open"}
          tone={allowedEmails.length > 0 ? "ready" : "warning"}
          detail={
            allowedEmails.length > 0
              ? `${allowedEmails.length} email(s) configured`
              : "Blank allowlist means any authenticated user can access admin."
          }
        />
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        {onboardingSteps.map((step, index) => (
          <article
            key={step.title}
            className="rounded-[1.5rem] border border-[#ece2e6] bg-white px-6 py-6 shadow-[0_16px_34px_rgba(10,37,64,0.04)]"
          >
            <div className="inline-flex rounded-full border border-[#eadbd4] bg-[#fff8f4] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-[#a65f41]">
              Step {index + 1}
            </div>
            <h3 className="mt-4 text-[1.18rem] font-bold tracking-[-0.04em] text-[#2d1870]">{step.title}</h3>
            <p className="mt-3 text-[0.95rem] leading-7 text-[#66788c]">{step.body}</p>

            <div className="mt-5 rounded-[1.2rem] border border-[#f0e5e3] bg-[#fcfaf7] px-4 py-4">
              <div className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#94a3b6]">Commands / locations</div>
              <div className="mt-3 space-y-2">
                {step.commands.map((command) => (
                  <code
                    key={command}
                    className="block overflow-x-auto rounded-[0.9rem] border border-[#eadfdc] bg-white px-3 py-3 text-[0.82rem] leading-6 text-[#33425a]"
                  >
                    {command}
                  </code>
                ))}
              </div>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}

function StatusCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: "ready" | "warning" | "missing";
}) {
  const toneClasses =
    tone === "ready"
      ? "border-[#cfe4d1] bg-[#eff8f1] text-[#2f7d3a]"
      : tone === "warning"
        ? "border-[#f2e0c8] bg-[#fff7ec] text-[#9d6a27]"
        : "border-[#eadbd4] bg-[#fff8f4] text-[#a65f41]";

  return (
    <div className="rounded-[1.2rem] border border-[#ece2e6] bg-white px-5 py-5 shadow-[0_12px_26px_rgba(10,37,64,0.04)]">
      <div className="text-[0.74rem] font-semibold uppercase tracking-[0.16em] text-[#94a3b6]">{label}</div>
      <div className="mt-3 flex items-center gap-3">
        <div className="text-[1.4rem] font-black tracking-[-0.05em] text-[#2d1870]">{value}</div>
        <div className={`rounded-full border px-3 py-1 text-[0.7rem] font-semibold uppercase tracking-[0.12em] ${toneClasses}`}>
          {tone}
        </div>
      </div>
      <div className="mt-3 text-[0.84rem] leading-6 text-[#69798b]">{detail}</div>
    </div>
  );
}
