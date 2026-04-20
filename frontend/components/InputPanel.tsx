"use client";

import { CompanyDashboardView } from "../lib/types";

type ListedFilter = "all" | "listed" | "unlisted";
type RatedFilter = "all" | "rated" | "unrated";
type SimulationFilter = "all" | "required" | "not_required";

type Props = {
  companyName: string;
  selectedFile: File | null;
  loading: boolean;
  mockMode: boolean;
  portfolioCompanies: CompanyDashboardView[];
  selectedCompanyId?: string | null;
  searchFilter: string;
  listedFilter: ListedFilter;
  ratedFilter: RatedFilter;
  simulationFilter: SimulationFilter;
  revenueMin: string;
  revenueMax: string;
  onCompanyNameChange: (value: string) => void;
  onFileChange: (file: File | null) => void;
  onProcessSingle: () => void;
  onProcessUpload: () => void;
  onProcessSamples: () => void;
  onClear: () => void;
  onSearchFilterChange: (value: string) => void;
  onListedFilterChange: (value: ListedFilter) => void;
  onRatedFilterChange: (value: RatedFilter) => void;
  onSimulationFilterChange: (value: SimulationFilter) => void;
  onRevenueMinChange: (value: string) => void;
  onRevenueMaxChange: (value: string) => void;
  onSelectCompany: (company: CompanyDashboardView) => void;
};

export function InputPanel({
  companyName,
  selectedFile,
  loading,
  mockMode,
  portfolioCompanies,
  selectedCompanyId,
  searchFilter,
  listedFilter,
  ratedFilter,
  simulationFilter,
  revenueMin,
  revenueMax,
  onCompanyNameChange,
  onFileChange,
  onProcessSingle,
  onProcessUpload,
  onProcessSamples,
  onClear,
  onSearchFilterChange,
  onListedFilterChange,
  onRatedFilterChange,
  onSimulationFilterChange,
  onRevenueMinChange,
  onRevenueMaxChange,
  onSelectCompany
}: Props) {
  return (
    <aside className="sidebar-panel">
      <div className="sidebar-topline">
        <div>
          <span className="sidebar-kicker">Underwriting Workbench</span>
          <h2>Bulk credit review</h2>
          <p className="sidebar-intro">Queue companies, narrow the portfolio, and move straight into exports.</p>
        </div>
        <div className="shell-statuses">
          <span className="status-chip">API Wrapper</span>
          <span className={`status-chip ${mockMode ? "is-warning" : "is-live"}`}>
            {mockMode ? "Mock Mode" : "Live Backend"}
          </span>
        </div>
      </div>

      <section className="sidebar-section">
        <div className="section-header">
          <span className="block-label">Search</span>
          <h3>Single company</h3>
        </div>
        <div className="sidebar-stack">
          <input
            value={companyName}
            onChange={(event) => onCompanyNameChange(event.target.value)}
            placeholder="Enter company name"
            aria-label="Company name"
          />
          <button onClick={onProcessSingle} disabled={loading || !companyName.trim()}>
            {loading ? "Processing..." : "Process Company"}
          </button>
        </div>
      </section>

      <section className="sidebar-section">
        <div className="section-header">
          <span className="block-label">Upload Portfolio</span>
          <h3>Batch processing</h3>
        </div>
        <div className="sidebar-stack">
          <input
            type="file"
            accept=".csv,.xlsx,.xls"
            onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
            aria-label="Upload portfolio file"
          />
          <span className="sidebar-help">{selectedFile ? selectedFile.name : "No file selected"}</span>
          <div className="sidebar-actions">
            <button className="secondary" onClick={onProcessUpload} disabled={loading || !selectedFile}>
              Process File
            </button>
            <button className="secondary" onClick={onProcessSamples} disabled={loading}>
              Load Sample
            </button>
            <button className="ghost" onClick={onClear} disabled={loading}>
              Clear
            </button>
          </div>
        </div>
      </section>

      <section className="sidebar-section">
        <div className="section-header">
          <span className="block-label">Portfolio Navigation</span>
          <h3>{portfolioCompanies.length} companies</h3>
        </div>
        <div className="portfolio-nav">
          {portfolioCompanies.length ? (
            portfolioCompanies.map((company) => {
              const companyKey = company.company_id ?? company.company_name;
              const isSelected = companyKey === selectedCompanyId;
              return (
                <button
                  key={companyKey}
                  className={`portfolio-nav-item ${isSelected ? "is-selected" : ""}`}
                  onClick={() => onSelectCompany(company)}
                >
                  <strong>{company.company_name}</strong>
                  <span>{company.ratings.rating ?? company.simulation.rating_range ?? "Awaiting review"}</span>
                </button>
              );
            })
          ) : (
            <p className="empty-sidebar">Upload or search to populate this list.</p>
          )}
        </div>
      </section>

      <section className="sidebar-section">
        <div className="section-header">
          <span className="block-label">Filters</span>
          <h3>Refine portfolio</h3>
        </div>
        <div className="sidebar-filter-grid">
          <label>
            <span>Search</span>
            <input
              value={searchFilter}
              onChange={(event) => onSearchFilterChange(event.target.value)}
              placeholder="Filter by company"
            />
          </label>
          <label>
            <span>Listed</span>
            <select value={listedFilter} onChange={(event) => onListedFilterChange(event.target.value as ListedFilter)}>
              <option value="all">All</option>
              <option value="listed">Listed</option>
              <option value="unlisted">Unlisted</option>
            </select>
          </label>
          <label>
            <span>Rated</span>
            <select value={ratedFilter} onChange={(event) => onRatedFilterChange(event.target.value as RatedFilter)}>
              <option value="all">All</option>
              <option value="rated">Rated</option>
              <option value="unrated">Unrated</option>
            </select>
          </label>
          <label>
            <span>Simulation</span>
            <select
              value={simulationFilter}
              onChange={(event) => onSimulationFilterChange(event.target.value as SimulationFilter)}
            >
              <option value="all">All</option>
              <option value="required">Required</option>
              <option value="not_required">Not required</option>
            </select>
          </label>
          <label>
            <span>Revenue Min (Cr)</span>
            <input value={revenueMin} onChange={(event) => onRevenueMinChange(event.target.value)} placeholder="0" />
          </label>
          <label>
            <span>Revenue Max (Cr)</span>
            <input value={revenueMax} onChange={(event) => onRevenueMaxChange(event.target.value)} placeholder="10000" />
          </label>
        </div>
      </section>
    </aside>
  );
}
