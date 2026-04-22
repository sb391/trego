import Link from "next/link";

import { searchAgriCompanies } from "../../../lib/admin/data";

type SearchParamsValue = string | string[] | undefined;

export default async function AdminAgriCompaniesPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, SearchParamsValue>>;
}) {
  const params = searchParams ? await searchParams : {};
  const query = typeof params.q === "string" ? params.q : "";
  const rows = await searchAgriCompanies(query);
  const spotlight = rows[0];
  const ratedCount = rows.filter((row) => row.latest_cra_rating && row.latest_cra_rating_status?.toLowerCase() !== "not rated").length;
  const simulationCount = rows.filter((row) => row.simulated_rating || row.published_range).length;

  return (
    <div className="space-y-6">
      <section className="rounded-[1.6rem] border border-[#ece2e6] bg-white px-6 py-6 shadow-[0_16px_34px_rgba(10,37,64,0.04)]">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-[#b86140]">Agri master</p>
            <h2 className="mt-2 text-[1.55rem] font-extrabold tracking-[-0.05em] text-[#2d1870]">
              Search the listed agri export exactly the way the underwriting service was built.
            </h2>
            <p className="mt-3 text-[0.95rem] leading-7 text-[#69798b]">
              Search by company name to see listed status, actual rating discovery, company secretary details, and the
              current simulated rating fields in one place.
            </p>
          </div>

          <form className="flex w-full max-w-xl flex-col gap-3 sm:flex-row">
            <input
              type="text"
              name="q"
              defaultValue={query}
              placeholder="Search company, agency, or industry"
              className="w-full rounded-[0.95rem] border border-[#e4d9de] bg-[#fcfaf8] px-4 py-3.5 text-[0.96rem] text-[#182039] outline-none transition focus:border-[#d1c2c7]"
            />
            <button
              type="submit"
              className="interactive-press rounded-[0.95rem] border border-[#7f3922] bg-[#853921] px-5 py-3.5 text-[0.76rem] font-semibold uppercase tracking-[0.1em] text-white shadow-[0_12px_22px_rgba(133,57,33,0.22)]"
            >
              Search
            </button>
          </form>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <Stat label="Matches" value={rows.length.toLocaleString("en-IN")} />
        <Stat label="Actual ratings found" value={ratedCount.toLocaleString("en-IN")} />
        <Stat label="Simulation outputs" value={simulationCount.toLocaleString("en-IN")} />
      </section>

      {spotlight ? (
        <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[1.5rem] border border-[#ece2e6] bg-white px-6 py-6 shadow-[0_16px_34px_rgba(10,37,64,0.04)]">
            <div className="text-[0.74rem] font-semibold uppercase tracking-[0.22em] text-[#b86140]">Company spotlight</div>
            <h3 className="mt-3 text-[1.45rem] font-extrabold tracking-[-0.04em] text-[#2d1870]">{spotlight.company_name}</h3>
            <div className="mt-2 text-[0.95rem] text-[#69798b]">
              {(spotlight.industry_name ?? spotlight.industry_group ?? "Industry not mapped") as string}
            </div>
            {spotlight.screener_url ? (
              <a
                href={spotlight.screener_url as string}
                target="_blank"
                rel="noreferrer"
                className="mt-4 inline-flex items-center text-[0.78rem] font-semibold uppercase tracking-[0.12em] text-[#b86140]"
              >
                Open Screener profile
              </a>
            ) : null}

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <Stat label="Listed status" value={(spotlight.listed_status ?? "Listed") as string} />
              <Stat label="Revenue (Cr)" value={formatNumber(spotlight.revenue_crore)} />
              <Stat label="EBITDA %" value={formatNumber(spotlight.ebitda_margin_pct)} />
              <Stat label="Debt / Equity" value={formatNumber(spotlight.debt_to_equity)} />
              <Stat label="Actual rating" value={(spotlight.latest_cra_rating ?? "Not rated") as string} />
              <Stat label="Simulation" value={(spotlight.simulated_rating ?? "Pending") as string} />
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-[#ece2e6] bg-white px-6 py-6 shadow-[0_16px_34px_rgba(10,37,64,0.04)]">
            <div className="text-[0.74rem] font-semibold uppercase tracking-[0.22em] text-[#b86140]">Decision inputs</div>
            <dl className="mt-5 space-y-4 text-[0.94rem] leading-7 text-[#607182]">
              <Meta label="Agency">{(spotlight.latest_cra_rating_agency ?? "—") as string}</Meta>
              <Meta label="Rating date">{(spotlight.latest_cra_rating_month_year ?? spotlight.latest_cra_rating_date ?? "—") as string}</Meta>
              <Meta label="Published range">{(spotlight.published_range ?? spotlight.calibrated_range ?? "—") as string}</Meta>
              <Meta label="Confidence">{(spotlight.range_confidence_label ?? "—") as string}</Meta>
              <Meta label="Review priority">{(spotlight.ca_review_priority ?? "—") as string}</Meta>
              <Meta label="Company secretary">{(spotlight.company_secretary_name ?? "—") as string}</Meta>
              <Meta label="Secretary contact">{(spotlight.company_secretary_contact_details ?? "—") as string}</Meta>
            </dl>
          </div>
        </section>
      ) : null}

      <section className="rounded-[1.5rem] border border-[#ece2e6] bg-white shadow-[0_16px_34px_rgba(10,37,64,0.04)]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#f0e5e3] px-6 py-4">
          <div className="text-[0.86rem] font-semibold uppercase tracking-[0.18em] text-[#90a2b6]">
            {rows.length} matched rows
          </div>
          <Link
            href="/api/admin/exports/agri-master"
            className="interactive-press rounded-[0.8rem] border border-[#e3d6d4] bg-[#fcfaf7] px-4 py-2.5 text-[0.72rem] font-semibold uppercase tracking-[0.12em] text-[#6f6176]"
          >
            Download agri master CSV
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-left">
            <thead className="bg-[#fcfaf7] text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-[#93a3b7]">
              <tr>
                {["Company", "Industry", "Revenue", "Debt/Equity", "Actual rating", "Simulation", "Priority"].map((header) => (
                  <th key={header} className="px-6 py-4">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#f2e7e4] text-[0.95rem] text-[#243047]">
              {rows.map((row) => (
                <tr key={row.company_id}>
                  <td className="px-6 py-5">
                    <div className="font-semibold">{row.company_name}</div>
                    <div className="mt-1 text-[0.86rem] text-[#69798b]">{row.nse_code ?? row.bse_code ?? "Listed company"}</div>
                  </td>
                  <td className="px-6 py-5 text-[#66788c]">{row.industry_name ?? row.industry_group ?? "—"}</td>
                  <td className="px-6 py-5">{formatNumber(row.revenue_crore)}</td>
                  <td className="px-6 py-5">{formatNumber(row.debt_to_equity)}</td>
                  <td className="px-6 py-5">
                    {(row.latest_cra_rating_agency ?? "—") as string}
                    <div className="mt-1 text-[0.86rem] text-[#69798b]">{(row.latest_cra_rating ?? "Not rated") as string}</div>
                  </td>
                  <td className="px-6 py-5">
                    {(row.simulated_rating_agency ?? "Model") as string}
                    <div className="mt-1 text-[0.86rem] text-[#69798b]">{(row.simulated_rating ?? "Pending") as string}</div>
                  </td>
                  <td className="px-6 py-5">
                    <span className="rounded-full border border-[#eadbd4] bg-[#fff8f4] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-[#a65f41]">
                      {(row.ca_review_priority ?? "—") as string}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1rem] border border-[#eee3e1] bg-white px-4 py-4 shadow-[0_10px_22px_rgba(10,37,64,0.03)]">
      <div className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-[#90a2b6]">{label}</div>
      <div className="mt-2 text-[1.1rem] font-bold tracking-[-0.03em] text-[#2d1870]">{value}</div>
    </div>
  );
}

function Meta({ label, children }: { label: string; children: string }) {
  return (
    <div>
      <dt className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#90a2b6]">{label}</dt>
      <dd className="mt-1 text-[#2a3550]">{children}</dd>
    </div>
  );
}

function formatNumber(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "number") {
    return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }
  return String(value);
}
