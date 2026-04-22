import Link from "next/link";

import { InquiryWorkflowTable } from "../../../components/admin/InquiryWorkflowTable";
import { getInquiryRows } from "../../../lib/admin/data";

export default async function AdminInquiriesPage() {
  const { rows, source } = await getInquiryRows(100);
  const newCount = rows.filter((row) => row.status === "new").length;
  const simulationCount = rows.filter((row) => row.inquiry_type === "Credit Rating Simulation").length;

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 rounded-[1.6rem] border border-[#ece2e6] bg-white px-6 py-6 shadow-[0_16px_34px_rgba(10,37,64,0.04)] sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-[#b86140]">Inquiries</p>
          <h2 className="mt-2 text-[1.55rem] font-extrabold tracking-[-0.05em] text-[#2d1870]">Submitted leads and follow-up queue</h2>
          <p className="mt-3 max-w-2xl text-[0.95rem] leading-7 text-[#69798b]">
            Website inquiries now land here. Until Supabase is configured, local development submissions are still
            captured and listed in seed mode.
          </p>
        </div>
        <Link
          href="/api/admin/exports/inquiries"
          className="interactive-press inline-flex items-center justify-center rounded-[0.95rem] border border-[#7f3922] bg-[#853921] px-5 py-3 text-[0.76rem] font-semibold uppercase tracking-[0.1em] text-white shadow-[0_12px_22px_rgba(133,57,33,0.22)]"
        >
          Download inquiries CSV
        </Link>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <MiniCard label="Open inquiries" value={String(newCount)} />
        <MiniCard label="Simulation requests" value={String(simulationCount)} />
        <MiniCard label="Records visible" value={String(rows.length)} />
      </section>

      <InquiryWorkflowTable initialRows={rows} workflowEnabled={source === "supabase"} />
    </div>
  );
}

function MiniCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.2rem] border border-[#ece2e6] bg-white px-5 py-5 shadow-[0_12px_26px_rgba(10,37,64,0.04)]">
      <div className="text-[1.45rem] font-black tracking-[-0.05em] text-[#2d1870]">{value}</div>
      <div className="mt-2 text-[0.74rem] font-semibold uppercase tracking-[0.16em] text-[#94a3b6]">{label}</div>
    </div>
  );
}
