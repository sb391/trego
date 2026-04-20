"use client";

import { useMemo, useState } from "react";

import { buildAbsoluteUrl } from "../lib/api";
import { formatCurrencyCr, formatDateLabel, formatNumber, formatPercent, listedLabel, riskToneClass } from "../lib/format";
import { CompanyDashboardView } from "../lib/types";
import { Sparkline } from "./Sparkline";

type Props = {
  company: CompanyDashboardView | null;
};

type TabKey = "overview" | "financials" | "ratings" | "treds" | "simulation" | "advisory";

function SummaryCard({
  title,
  value,
  detail,
  tone = "neutral"
}: {
  title: string;
  value: string;
  detail: string;
  tone?: string;
}) {
  return (
    <div className={`summary-card ${riskToneClass(tone)}`}>
      <span className="summary-label">{title}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </div>
  );
}

function OverviewMetric({
  label,
  value
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="overview-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DataTable({
  title,
  rows
}: {
  title: string;
  rows: Array<Record<string, unknown>>;
}) {
  if (!rows.length) {
    return (
      <div className="data-card">
        <div className="data-card-head">
          <h3>{title}</h3>
        </div>
        <p className="empty-state">No rows available.</p>
      </div>
    );
  }

  const columns = Array.from(
    rows.reduce((set, row) => {
      Object.keys(row).forEach((key) => set.add(key));
      return set;
    }, new Set<string>())
  ).slice(0, 8);

  return (
    <div className="data-card">
      <div className="data-card-head">
        <h3>{title}</h3>
        <span>{rows.length} rows</span>
      </div>
      <div className="table-wrap">
        <table className="compact-grid">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column.replaceAll("_", " ")}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 10).map((row, index) => (
              <tr key={`${title}-${index}`}>
                {columns.map((column) => {
                  const value = row[column];
                  return <td key={column}>{typeof value === "number" ? formatNumber(value) : String(value ?? "—")}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function DetailView({ company }: Props) {
  const [tab, setTab] = useState<TabKey>("overview");

  const content = useMemo(() => {
    if (!company) {
      return <p className="empty-state">Select a company from the portfolio table to open the dashboard.</p>;
    }

    if (tab === "overview") {
      return (
        <div className="detail-stack">
          <div className="overview-grid">
            <OverviewMetric label="Requested Name" value={company.requested_name} />
            <OverviewMetric label="Industry" value={company.industry ?? "—"} />
            <OverviewMetric label="Listed Status" value={listedLabel(company.listed_status)} />
            <OverviewMetric label="Revenue" value={formatCurrencyCr(company.revenue)} />
            <OverviewMetric label="Turnover" value={formatCurrencyCr(company.turnover_crore)} />
            <OverviewMetric label="Processed At" value={formatDateLabel(company.processed_at)} />
          </div>
          <div className="trend-grid">
            <Sparkline title="Revenue Trend" points={company.financials.trend_series.revenue ?? []} />
            <Sparkline title="Net Profit Trend" points={company.financials.trend_series.net_profit ?? []} stroke="#3fa7d6" />
            <Sparkline title="OPM Trend" points={company.financials.trend_series.opm_percent ?? []} stroke="#77b255" />
          </div>
          <div className="data-card">
            <div className="data-card-head">
              <h3>Our Rationale</h3>
              <span>{company.advisory.rationale_sections.length} sections</span>
            </div>
            {company.advisory.rationale_sections.length ? (
              <div className="detail-stack">
                {company.advisory.rationale_sections.map((section) => (
                  <div className="rationale-block" key={section.heading}>
                    <h4>{section.heading}</h4>
                    <p>{section.body}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p>{company.advisory.rationale_draft ?? "No rationale narrative available."}</p>
            )}
          </div>
        </div>
      );
    }

    if (tab === "financials") {
      return (
        <div className="detail-stack">
          <div className="overview-grid">
            <OverviewMetric label="EBITDA Margin" value={formatPercent(company.financials.summary.ebitda_margin_pct)} />
            <OverviewMetric label="PAT Margin" value={formatPercent(company.financials.summary.pat_margin_pct)} />
            <OverviewMetric label="Debt / Equity" value={formatNumber(company.financials.summary.debt_to_equity)} />
            <OverviewMetric label="Interest Coverage" value={formatNumber(company.financials.summary.interest_coverage)} />
            <OverviewMetric label="WC Days" value={formatNumber(company.financials.summary.working_capital_days)} />
            <OverviewMetric label="Market Cap" value={formatCurrencyCr(company.financials.summary.market_cap_crore)} />
          </div>
          <div className="trend-grid">
            <Sparkline title="Revenue Trend" points={company.financials.trend_series.revenue ?? []} />
            <Sparkline title="Net Profit Trend" points={company.financials.trend_series.net_profit ?? []} stroke="#3fa7d6" />
            <Sparkline title="OPM Trend" points={company.financials.trend_series.opm_percent ?? []} stroke="#77b255" />
          </div>
          <DataTable title="Profit & Loss" rows={company.financials.tables.profit_loss ?? []} />
          <DataTable title="Quarterly Results" rows={company.financials.tables.quarterly_results ?? []} />
          <DataTable title="Balance Sheet" rows={company.financials.tables.balance_sheet ?? []} />
          <DataTable title="Cash Flow" rows={company.financials.tables.cash_flow ?? []} />
        </div>
      );
    }

    if (tab === "ratings") {
      return (
        <div className="detail-stack">
          <div className="overview-grid">
            <OverviewMetric label="Latest Rating" value={company.ratings.rating ?? "—"} />
            <OverviewMetric label="Agency" value={company.ratings.agency ?? "—"} />
            <OverviewMetric label="Outlook" value={company.ratings.outlook ?? "—"} />
            <OverviewMetric label="Rating Date" value={formatDateLabel(company.ratings.rating_date)} />
            <OverviewMetric label="Action" value={company.ratings.rating_action ?? "—"} />
            <OverviewMetric label="Status" value={company.ratings.status} />
          </div>
          <div className="data-card">
            <div className="data-card-head">
              <h3>Rating History</h3>
              <span>{company.ratings.history.length} entries</span>
            </div>
            <div className="table-wrap">
              <table className="compact-grid">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Agency</th>
                    <th>Rating</th>
                    <th>Outlook</th>
                    <th>Action</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {company.ratings.history.length ? (
                    company.ratings.history.map((entry, index) => (
                      <tr key={`${entry.rating_date}-${index}`}>
                        <td>{formatDateLabel(entry.rating_date)}</td>
                        <td>{entry.agency_name ?? "—"}</td>
                        <td>{entry.rating ?? "—"}</td>
                        <td>{entry.outlook ?? "—"}</td>
                        <td>{entry.rating_action ?? "—"}</td>
                        <td>{entry.source ?? "—"}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6}>No rating history available.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
          {company.ratings.notes.length ? (
            <div className="data-card">
              <div className="data-card-head">
                <h3>Rating Notes</h3>
              </div>
              <ul className="signal-list">
                {company.ratings.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      );
    }

    if (tab === "treds") {
      return (
        <div className="detail-stack">
          <div className="overview-grid">
            <OverviewMetric label="Status" value={company.tred.status} />
            <OverviewMetric label="Platforms" value={company.tred.platforms.join(", ") || "—"} />
            <OverviewMetric label="Signal Strength" value={company.tred.signal_strength} />
            <OverviewMetric label="Estimated Limit" value={formatCurrencyCr(company.tred.estimated_limit_crore)} />
            <OverviewMetric label="Confidence" value={company.tred.estimation_confidence ?? "—"} />
            <OverviewMetric label="Method" value={company.tred.method_used ?? "—"} />
          </div>
          <div className="data-card">
            <div className="data-card-head">
              <h3>Raw TReDS Mentions</h3>
              <span>{company.tred.raw_mentions.length} signals</span>
            </div>
            {company.tred.raw_mentions.length ? (
              <ul className="signal-list">
                {company.tred.raw_mentions.map((mention) => (
                  <li key={mention}>{mention}</li>
                ))}
              </ul>
            ) : (
              <p className="empty-state">No raw public mentions were provided in the current response.</p>
            )}
          </div>
        </div>
      );
    }

    if (tab === "simulation") {
      return (
        <div className="detail-stack">
          <div className="overview-grid">
            <OverviewMetric label="Required" value={company.simulation.required_flag ? "Yes" : "No"} />
            <OverviewMetric label="Status" value={company.simulation.status} />
            <OverviewMetric label="Simulated Rating" value={company.simulation.simulated_rating ?? "—"} />
            <OverviewMetric label="Range" value={company.simulation.rating_range ?? "—"} />
            <OverviewMetric label="Confidence" value={company.simulation.confidence_label ?? "—"} />
            <OverviewMetric label="Method" value={company.simulation.method_used ?? "—"} />
          </div>
          <div className="data-card">
            <div className="data-card-head">
              <h3>Simulation Notes</h3>
            </div>
            {company.simulation.notes.length ? (
              <ul className="signal-list">
                {company.simulation.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            ) : (
              <p className="empty-state">No simulation notes were supplied by the backend.</p>
            )}
          </div>
        </div>
      );
    }

    return (
      <div className="detail-stack">
        <div className="data-card">
          <div className="data-card-head">
            <h3>Advisory Notes</h3>
            <span>{company.advisory.notes.length} items</span>
          </div>
          {company.advisory.notes.length ? (
            <ul className="signal-list">
              {company.advisory.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : (
            <p className="empty-state">No advisory notes were supplied.</p>
          )}
        </div>

        <div className="data-card">
          <div className="data-card-head">
            <h3>Processing Notes</h3>
            <span>{company.advisory.processing_notes.length} items</span>
          </div>
          {company.advisory.processing_notes.length ? (
            <ul className="signal-list">
              {company.advisory.processing_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : (
            <p className="empty-state">No processing notes recorded.</p>
          )}
        </div>
      </div>
    );
  }, [company, tab]);

  if (!company) {
    return (
      <section className="panel detail-panel">
        <div className="panel-head">
          <div>
            <span className="section-kicker">Dashboard</span>
            <h2>Company view</h2>
          </div>
        </div>
        <p className="empty-state">Select a company from the portfolio table to inspect the full dashboard.</p>
      </section>
    );
  }

  const excelUrl = buildAbsoluteUrl(company.downloads.excel_url);
  const pdfUrl = buildAbsoluteUrl(company.downloads.pdf_url);
  const wordUrl = buildAbsoluteUrl(company.downloads.word_url);

  return (
    <section className="panel detail-panel">
      <div className="dashboard-top">
        <div>
          <span className="section-kicker">Company Dashboard</span>
          <h2>{company.company_name}</h2>
          <p>
            {company.industry ?? "Industry not available"} · {listedLabel(company.listed_status)} · Processed{" "}
            {formatDateLabel(company.processed_at)}
          </p>
        </div>
        <div className="export-actions">
          <button onClick={() => excelUrl && window.open(excelUrl, "_blank")}>Excel</button>
          <button className="secondary" onClick={() => pdfUrl && window.open(pdfUrl, "_blank")}>
            PDF
          </button>
          <button className="ghost" onClick={() => wordUrl && window.open(wordUrl, "_blank")}>
            Word
          </button>
        </div>
      </div>

      <div className="summary-card-grid">
        <SummaryCard
          title="Rating"
          value={company.ratings.rating ?? "Not Available"}
          detail={`${company.ratings.agency ?? "No agency"} · ${company.ratings.outlook ?? "No outlook"}`}
          tone={company.ratings.available_flag ? "low" : "medium"}
        />
        <SummaryCard
          title="Simulation"
          value={company.simulation.rating_range ?? company.simulation.status}
          detail={company.simulation.simulated_rating ?? company.simulation.method_used ?? "Awaiting backend output"}
          tone={company.simulation.required_flag ? "medium" : "low"}
        />
        <SummaryCard
          title="TReDS"
          value={company.tred.status}
          detail={`${company.tred.signal_strength} signal · ${formatCurrencyCr(company.tred.estimated_limit_crore)}`}
          tone={company.tred.presence_flag ? "low" : "neutral"}
        />
        <SummaryCard
          title="Risk Snapshot"
          value={company.risk_indicator.label}
          detail={company.risk_indicator.reasons[0] ?? "No immediate flag supplied"}
          tone={company.risk_indicator.tone}
        />
      </div>

      <div className="tab-bar">
        {(["overview", "financials", "ratings", "treds", "simulation", "advisory"] as TabKey[]).map((key) => (
          <button
            key={key}
            className={tab === key ? "tab-button is-active" : "tab-button"}
            onClick={() => setTab(key)}
          >
            {key === "treds" ? "TReDS" : key.charAt(0).toUpperCase() + key.slice(1)}
          </button>
        ))}
      </div>

      {content}
    </section>
  );
}
