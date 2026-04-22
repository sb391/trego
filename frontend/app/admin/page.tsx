import Link from "next/link";

import { getAdminSummary } from "../../lib/admin/data";

const cards = [
  { key: "inquiryCount", label: "Inquiries captured" },
  { key: "agriCompanyCount", label: "Agri companies indexed" },
  { key: "ratedCompanyCount", label: "Actual ratings found" },
  { key: "simulationRequiredCount", label: "Simulation-required cases" },
] as const;

export default async function AdminOverviewPage() {
  const summary = await getAdminSummary();

  return (
    <div className="space-y-8">
      <section className="rounded-[1.8rem] border border-[#ece2e6] bg-white px-6 py-7 shadow-[0_18px_40px_rgba(10,37,64,0.05)] sm:px-8 sm:py-8">
        <div className="max-w-3xl">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-[#b86140]">Readiness</p>
          <h2 className="mt-3 text-[1.65rem] font-extrabold tracking-[-0.05em] text-[#2d1870] sm:text-[2rem]">
            One place for inquiries, agri intelligence, and downloadable operating data.
          </h2>
          <p className="mt-4 max-w-2xl text-[0.96rem] leading-7 text-[#69798b]">
            This is the first pass of the operating layer: live inquiry persistence, a normalized agri company master,
            and admin routes ready for Supabase-backed internal workflows.
          </p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <div
            key={card.key}
            className="rounded-[1.4rem] border border-[#ece2e6] bg-white px-5 py-5 shadow-[0_14px_30px_rgba(10,37,64,0.04)]"
          >
            <div className="text-[1.8rem] font-black tracking-[-0.05em] text-[#2d1870]">
              {summary[card.key].toLocaleString("en-IN")}
            </div>
            <div className="mt-2 text-[0.78rem] font-semibold uppercase tracking-[0.18em] text-[#94a3b6]">
              {card.label}
            </div>
          </div>
        ))}
      </section>

      <section className="grid gap-5 lg:grid-cols-3">
        <QuickLinkCard
          href="/admin/inquiries"
          title="All submitted inquiries"
          body="Review inbound demand, monitor status, and export the current inquiry ledger."
        />
        <QuickLinkCard
          href="/admin/agri-companies"
          title="Agri intelligence"
          body="Search the agri master by company name and access the same major fields already built in the export service."
        />
        <QuickLinkCard
          href="/admin/exports"
          title="Exports and dumps"
          body="Download inquiries, the agri master, or the joined inquiry-plus-financial-data dump."
        />
        <QuickLinkCard
          href="/admin/setup"
          title="Supabase setup"
          body="Follow the exact migration, admin-auth, and seeding steps for this project before public launch."
        />
      </section>
    </div>
  );
}

function QuickLinkCard({ href, title, body }: { href: string; title: string; body: string }) {
  return (
    <Link
      href={href}
      className="interactive-press rounded-[1.5rem] border border-[#ece2e6] bg-[linear-gradient(180deg,#ffffff_0%,#fbf8f5_100%)] px-6 py-6 shadow-[0_16px_32px_rgba(10,37,64,0.04)] transition hover:-translate-y-0.5"
    >
      <div className="text-[1.15rem] font-bold tracking-[-0.04em] text-[#2d1870]">{title}</div>
      <p className="mt-3 text-[0.94rem] leading-7 text-[#66788c]">{body}</p>
      <div className="mt-5 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#b86140]">Open section</div>
    </Link>
  );
}
