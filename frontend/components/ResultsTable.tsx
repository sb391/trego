"use client";

import { buildAbsoluteUrl } from "../lib/api";
import { formatCurrencyCr, formatNumber, formatPercent, listedLabel, riskToneClass } from "../lib/format";
import { CompanyDashboardView } from "../lib/types";

type Props = {
  allCompanies: CompanyDashboardView[];
  companies: CompanyDashboardView[];
  selectedCompanyId?: string | null;
  onSelect: (company: CompanyDashboardView) => void;
  batchExcelUrl?: string | null;
  batchZipUrl?: string | null;
  currentPage: number;
  totalPages: number;
  pageStart: number;
  pageEnd: number;
  totalFiltered: number;
  onPreviousPage: () => void;
  onNextPage: () => void;
  onPageChange: (page: number) => void;
};

export function ResultsTable({
  allCompanies,
  companies,
  selectedCompanyId,
  onSelect,
  batchExcelUrl,
  batchZipUrl,
  currentPage,
  totalPages,
  pageStart,
  pageEnd,
  totalFiltered,
  onPreviousPage,
  onNextPage,
  onPageChange
}: Props) {
  const rated = allCompanies.filter((company) => company.ratings.available_flag).length;
  const awaitingSimulation = allCompanies.filter((company) => company.simulation.required_flag).length;
  const listed = allCompanies.filter((company) => company.listed_status === "listed").length;

  const excelLink = buildAbsoluteUrl(batchExcelUrl);
  const zipLink = buildAbsoluteUrl(batchZipUrl);
  const canDownloadBatch = Boolean(excelLink);
  const canDownloadZip = Boolean(zipLink);

  if (!allCompanies.length) {
    return (
      <section className="content-panel">
        <div className="portfolio-header">
          <div>
            <span className="section-kicker">Portfolio</span>
            <h2>No portfolio loaded</h2>
            <p>Upload a company list or process a company to populate the underwriting workspace.</p>
          </div>
        </div>
        <div className="empty-state wide">No rows to display yet.</div>
      </section>
    );
  }

  return (
    <section className="content-panel">
      <div className="portfolio-header">
        <div>
          <span className="section-kicker">Portfolio Header</span>
          <h2>Underwriting queue</h2>
          <p>Dense portfolio comparison surface with batch exports and row-level report actions.</p>
        </div>
        <div className="header-actions">
          <button
            className="secondary"
            onClick={() => {
              if (excelLink) {
                window.open(excelLink, "_blank");
              }
            }}
            disabled={!canDownloadBatch}
          >
            Download Batch Excel
          </button>
          <button
            onClick={() => {
              if (zipLink) {
                window.open(zipLink, "_blank");
              }
            }}
            disabled={!canDownloadZip}
          >
            Download All Reports (ZIP)
          </button>
        </div>
      </div>

      <div className="portfolio-count-strip">
        <div className="count-chip">
          <span>Total Processed</span>
          <strong>{allCompanies.length}</strong>
        </div>
        <div className="count-chip">
          <span>Listed</span>
          <strong>{listed}</strong>
        </div>
        <div className="count-chip">
          <span>Rated</span>
          <strong>{rated}</strong>
        </div>
        <div className="count-chip">
          <span>Awaiting Simulation</span>
          <strong>{awaitingSimulation}</strong>
        </div>
      </div>

      <div className="table-shell">
        <div className="table-wrap bloomberg-table-wrap">
          <table className="bloomberg-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Listed Status</th>
                <th>Revenue</th>
                <th>EBITDA %</th>
                <th>Debt/Equity</th>
                <th>Rating (Latest)</th>
                <th>Agency</th>
                <th>TReDS Status</th>
                <th>Estimated TReDS Limit</th>
                <th>Simulation Range</th>
                <th>Risk Indicator</th>
                <th>Reports</th>
              </tr>
            </thead>
            <tbody>
              {companies.length ? (
                companies.map((company) => {
                  const isSelected = (company.company_id || company.company_name) === selectedCompanyId;
                  return (
                    <tr
                      key={company.company_id ?? company.company_name}
                      className={isSelected ? "is-selected" : undefined}
                      onClick={() => onSelect(company)}
                    >
                      <td>
                        <div className="company-cell">
                          <strong>{company.company_name}</strong>
                          <span>{company.industry ?? "Industry n/a"}</span>
                        </div>
                      </td>
                      <td>{listedLabel(company.listed_status)}</td>
                      <td>{formatCurrencyCr(company.revenue)}</td>
                      <td>{formatPercent(company.financials.summary.ebitda_margin_pct)}</td>
                      <td>{formatNumber(company.financials.summary.debt_to_equity)}</td>
                      <td>{company.ratings.rating ?? "—"}</td>
                      <td>{company.ratings.agency ?? "—"}</td>
                      <td>{company.tred.status}</td>
                      <td>{formatCurrencyCr(company.tred.estimated_limit_crore)}</td>
                      <td>{company.simulation.rating_range ?? company.simulation.status}</td>
                      <td>
                        <span className={`risk-pill ${riskToneClass(company.risk_indicator.tone)}`}>
                          {company.risk_indicator.label}
                        </span>
                      </td>
                      <td>
                        <div className="row-actions">
                          <button
                            className="micro-button"
                            onClick={(event) => {
                              event.stopPropagation();
                              const link = buildAbsoluteUrl(company.downloads.excel_url);
                              if (link) {
                                window.open(link, "_blank");
                              }
                            }}
                          >
                            Export Excel
                          </button>
                          <button
                            className="micro-button"
                            onClick={(event) => {
                              event.stopPropagation();
                              const link = buildAbsoluteUrl(company.downloads.pdf_url);
                              if (link) {
                                window.open(link, "_blank");
                              }
                            }}
                          >
                            PDF
                          </button>
                          <button
                            className="micro-button"
                            onClick={(event) => {
                              event.stopPropagation();
                              const link = buildAbsoluteUrl(company.downloads.word_url);
                              if (link) {
                                window.open(link, "_blank");
                              }
                            }}
                          >
                            Word
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={12}>
                    <div className="empty-state">No companies match the current filters.</div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="pagination-bar">
        <span>
          Displaying {pageStart}-{pageEnd} of {totalFiltered}
        </span>
        <div className="pagination-actions">
          <button className="secondary" onClick={onPreviousPage} disabled={currentPage <= 1}>
            Previous
          </button>
          <div className="page-numbers">
            {buildVisiblePages(currentPage, totalPages).map((page) => (
              <button
                key={page}
                className={`page-button ${page === currentPage ? "is-active" : ""}`}
                onClick={() => onPageChange(page)}
              >
                {page}
              </button>
            ))}
          </div>
          <button className="secondary" onClick={onNextPage} disabled={currentPage >= totalPages}>
            Next
          </button>
        </div>
      </div>
    </section>
  );
}

function buildVisiblePages(currentPage: number, totalPages: number): number[] {
  if (totalPages <= 5) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const start = Math.max(1, currentPage - 2);
  const end = Math.min(totalPages, start + 4);
  const adjustedStart = Math.max(1, end - 4);
  return Array.from({ length: end - adjustedStart + 1 }, (_, index) => adjustedStart + index);
}
