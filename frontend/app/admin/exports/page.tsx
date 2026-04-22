import Link from "next/link";

import { buildJoinedInquiryDump, getAgriMasterRows, getInquiryRows } from "../../../lib/admin/data";

const exportCards = [
  {
    key: "inquiries",
    title: "Inquiry ledger",
    body: "All submitted website inquiries with timestamps, ownership, and current workflow notes.",
    href: "/api/admin/exports/inquiries",
  },
  {
    key: "agri",
    title: "Agri master",
    body: "The consolidated agri intelligence sheet with ratings, simulations, and company secretary information.",
    href: "/api/admin/exports/agri-master",
  },
  {
    key: "joined",
    title: "Joined inquiry dump",
    body: "Inquiry records left-joined against agri intelligence by normalized company name.",
    href: "/api/admin/exports/joined-dump",
  },
] as const;

export default async function AdminExportsPage() {
  const [{ rows: inquiryRows, source: inquirySource }, { rows: agriRows, source: agriSource }, joinedRows] =
    await Promise.all([getInquiryRows(), getAgriMasterRows(), buildJoinedInquiryDump()]);
  const exportCounts = {
    inquiries: inquiryRows.length,
    agri: agriRows.length,
    joined: joinedRows.length,
  };

  return (
    <div className="space-y-6">
      <section className="rounded-[1.6rem] border border-[#ece2e6] bg-white px-6 py-6 shadow-[0_16px_34px_rgba(10,37,64,0.04)]">
        <p className="text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-[#b86140]">Exports</p>
        <h2 className="mt-2 text-[1.55rem] font-extrabold tracking-[-0.05em] text-[#2d1870]">
          Download operating dumps for analysis and follow-through.
        </h2>
        <p className="mt-3 max-w-2xl text-[0.95rem] leading-7 text-[#69798b]">
          This is the first export layer: one file for inquiries, one for the agri intelligence master, and one joined
          dump that lets CAs review inbound demand against company-level financial and simulation context.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <MiniCard label="Inquiry rows" value={String(exportCounts.inquiries)} detail={`Source: ${inquirySource}`} />
        <MiniCard label="Agri records" value={String(exportCounts.agri)} detail={`Source: ${agriSource}`} />
        <MiniCard label="Joined rows" value={String(exportCounts.joined)} detail="Inquiry + intelligence dump" />
      </section>

      <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {exportCards.map((card) => (
          <ExportCard
            key={card.key}
            title={card.title}
            body={card.body}
            href={card.href}
            rowCount={exportCounts[card.key]}
          />
        ))}
      </section>
    </div>
  );
}

function MiniCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-[1.2rem] border border-[#ece2e6] bg-white px-5 py-5 shadow-[0_12px_26px_rgba(10,37,64,0.04)]">
      <div className="text-[1.45rem] font-black tracking-[-0.05em] text-[#2d1870]">{value}</div>
      <div className="mt-2 text-[0.74rem] font-semibold uppercase tracking-[0.16em] text-[#94a3b6]">{label}</div>
      <div className="mt-2 text-[0.82rem] leading-6 text-[#69798b]">{detail}</div>
    </div>
  );
}

function ExportCard({
  title,
  body,
  href,
  rowCount,
}: {
  title: string;
  body: string;
  href: string;
  rowCount: number;
}) {
  return (
    <div className="rounded-[1.5rem] border border-[#ece2e6] bg-white px-6 py-6 shadow-[0_16px_34px_rgba(10,37,64,0.04)]">
      <div className="text-[1.12rem] font-bold tracking-[-0.04em] text-[#2d1870]">{title}</div>
      <p className="mt-3 text-[0.94rem] leading-7 text-[#66788c]">{body}</p>
      <div className="mt-4 text-[0.82rem] font-medium text-[#7a8a9d]">{rowCount.toLocaleString("en-IN")} rows available</div>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          href={`${href}?format=csv`}
          className="interactive-press inline-flex items-center justify-center rounded-[0.92rem] border border-[#7f3922] bg-[#853921] px-4 py-3 text-[0.74rem] font-semibold uppercase tracking-[0.1em] text-white shadow-[0_12px_22px_rgba(133,57,33,0.22)]"
        >
          Download CSV
        </Link>
        <Link
          href={`${href}?format=json`}
          className="interactive-press inline-flex items-center justify-center rounded-[0.92rem] border border-[#d9cdd0] bg-[#fcfaf7] px-4 py-3 text-[0.74rem] font-semibold uppercase tracking-[0.1em] text-[#5f6f82]"
        >
          Download JSON
        </Link>
      </div>
    </div>
  );
}
