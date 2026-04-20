export type FinancialSummary = {
  revenue_crore?: number | null;
  ebitda_margin_pct?: number | null;
  pat_margin_pct?: number | null;
  debt_to_equity?: number | null;
  interest_coverage?: number | null;
  working_capital_days?: number | null;
  receivables_days?: number | null;
  inventory_days?: number | null;
  current_price?: number | null;
  market_cap_crore?: number | null;
  networth_crore?: number | null;
  total_borrowings_crore?: number | null;
  source?: string | null;
  statement_period?: string | null;
};

export type TrendPoint = {
  label: string;
  value?: number | null;
};

export type RatingHistoryEntry = {
  rating_date?: string | null;
  agency_name?: string | null;
  rating?: string | null;
  outlook?: string | null;
  rating_action?: string | null;
  source_url?: string | null;
  source?: string | null;
};

export type ReportLinks = {
  excel_url: string;
  pdf_url: string;
  word_url: string;
};

export type FinancialsView = {
  summary: FinancialSummary;
  tables: Record<string, Array<Record<string, unknown>>>;
  trend_series: Record<string, TrendPoint[]>;
};

export type RatingsView = {
  available_flag: boolean;
  status: string;
  rating?: string | null;
  agency?: string | null;
  outlook?: string | null;
  rating_date?: string | null;
  rating_action?: string | null;
  history: RatingHistoryEntry[];
  notes: string[];
};

export type TredsView = {
  presence_flag: boolean;
  status: string;
  platforms: string[];
  signal_strength: string;
  estimated_limit_crore?: number | null;
  estimation_confidence?: string | null;
  method_used?: string | null;
  raw_mentions: string[];
};

export type SimulationView = {
  required_flag: boolean;
  status: string;
  simulated_rating?: string | null;
  rating_range?: string | null;
  confidence_label?: string | null;
  method_used?: string | null;
  notes: string[];
};

export type RationaleSection = {
  heading: string;
  body: string;
};

export type AdvisoryView = {
  notes: string[];
  rationale_sections: RationaleSection[];
  rationale_draft?: string | null;
  processing_notes: string[];
};

export type RiskIndicatorView = {
  label: string;
  tone: string;
  reasons: string[];
};

export type CompanyDashboardView = {
  company_id?: string | null;
  company_name: string;
  requested_name: string;
  industry?: string | null;
  listed_status: string;
  revenue?: number | null;
  turnover_crore?: number | null;
  below_threshold_flag: boolean;
  processed_at?: string | null;
  financials: FinancialsView;
  ratings: RatingsView;
  tred: TredsView;
  simulation: SimulationView;
  advisory: AdvisoryView;
  risk_indicator: RiskIndicatorView;
  downloads: ReportLinks;
};

export type PortfolioBatchView = {
  batch_id: string;
  company_count: number;
  companies: CompanyDashboardView[];
  batch_excel_url?: string | null;
  batch_zip_url?: string | null;
  workbook_path?: string | null;
  mock_mode?: boolean;
};
