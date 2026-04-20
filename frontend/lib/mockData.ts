import { CompanyDashboardView, PortfolioBatchView, TrendPoint } from "./types";

function trend(values: Array<[string, number]>): TrendPoint[] {
  return values.map(([label, value]) => ({ label, value }));
}

function buildMockCompany(
  companyName: string,
  index: number,
  overrides?: Partial<CompanyDashboardView>
): CompanyDashboardView {
  const baseRevenue = 420 + index * 135;
  const ebitda = 8.4 + index * 0.9;
  const debt = 0.7 + index * 0.25;
  const estimatedLimit = 62 + index * 18;

  return {
    company_id: `mock-${index + 1}`,
    company_name: companyName,
    requested_name: companyName,
    industry: index % 2 === 0 ? "Agricultural Products" : "Edible Oils",
    listed_status: index % 3 === 0 ? "listed" : "unlisted",
    revenue: baseRevenue,
    turnover_crore: baseRevenue,
    below_threshold_flag: false,
    processed_at: "2026-04-16T16:30:00+00:00",
    financials: {
      summary: {
        revenue_crore: baseRevenue,
        ebitda_margin_pct: ebitda,
        pat_margin_pct: 3.2 + index * 0.4,
        debt_to_equity: debt,
        interest_coverage: 2.6 + index * 0.5,
        working_capital_days: 88 + index * 17,
        receivables_days: 39 + index * 7,
        inventory_days: 28 + index * 5,
        market_cap_crore: 980 + index * 220,
        total_borrowings_crore: 120 + index * 32,
        statement_period: "2025-03-31"
      },
      tables: {
        profit_loss: [
          { period: "2022-03-31", sales: baseRevenue - 140, net_profit: 12 + index * 2, opm_percent: ebitda - 1.7 },
          { period: "2023-03-31", sales: baseRevenue - 85, net_profit: 15 + index * 2.2, opm_percent: ebitda - 0.9 },
          { period: "2024-03-31", sales: baseRevenue - 35, net_profit: 18 + index * 2.4, opm_percent: ebitda - 0.4 },
          { period: "2025-03-31", sales: baseRevenue, net_profit: 23 + index * 2.8, opm_percent: ebitda }
        ],
        balance_sheet: [
          { period: "2024-03-31", reserves: 112 + index * 20, borrowings: 96 + index * 18, total_assets: 260 + index * 44 },
          { period: "2025-03-31", reserves: 138 + index * 26, borrowings: 120 + index * 22, total_assets: 308 + index * 52 }
        ],
        cash_flow: [
          { period: "2024-03-31", cash_from_operating_activity: 28 + index * 6, cash_from_investing_activity: -14 - index * 3 },
          { period: "2025-03-31", cash_from_operating_activity: 31 + index * 7, cash_from_investing_activity: -18 - index * 3.5 }
        ],
        quarterly_results: [
          { period: "Jun 2025", sales: 102 + index * 21, net_profit: 5.1 + index * 0.8 },
          { period: "Sep 2025", sales: 110 + index * 24, net_profit: 5.8 + index * 0.9 },
          { period: "Dec 2025", sales: 124 + index * 25, net_profit: 6.4 + index * 1.0 }
        ]
      },
      trend_series: {
        revenue: trend([
          ["FY22", baseRevenue - 140],
          ["FY23", baseRevenue - 85],
          ["FY24", baseRevenue - 35],
          ["FY25", baseRevenue]
        ]),
        net_profit: trend([
          ["FY22", 12 + index * 2],
          ["FY23", 15 + index * 2.2],
          ["FY24", 18 + index * 2.4],
          ["FY25", 23 + index * 2.8]
        ]),
        opm_percent: trend([
          ["FY22", ebitda - 1.7],
          ["FY23", ebitda - 0.9],
          ["FY24", ebitda - 0.4],
          ["FY25", ebitda]
        ])
      }
    },
    ratings: {
      available_flag: index % 2 === 0,
      status: index % 2 === 0 ? "available" : "not_available",
      rating: index % 2 === 0 ? "BBB+" : null,
      agency: index % 2 === 0 ? "CRISIL" : null,
      outlook: index % 2 === 0 ? "Stable" : null,
      rating_date: index % 2 === 0 ? "2025-07-02" : null,
      rating_action: index % 2 === 0 ? "Reaffirmed" : null,
      history:
        index % 2 === 0
          ? [
              { rating_date: "2025-07-02", agency_name: "CRISIL", rating: "BBB+", outlook: "Stable", rating_action: "Reaffirmed" },
              { rating_date: "2024-06-12", agency_name: "CRISIL", rating: "BBB", outlook: "Stable", rating_action: "Upgraded" }
            ]
          : [],
      notes: index % 2 === 0 ? ["Latest external rating captured from backend response."] : ["No external rating found in the current response."]
    },
    tred: {
      presence_flag: index % 2 === 0,
      status: index % 2 === 0 ? "Observed" : "Estimated",
      platforms: index % 2 === 0 ? ["RXIL", "M1xchange"] : [],
      signal_strength: index % 2 === 0 ? "high" : "medium",
      estimated_limit_crore: estimatedLimit,
      estimation_confidence: index % 2 === 0 ? "high" : "medium",
      method_used: index % 2 === 0 ? "proxy" : "model",
      raw_mentions: index % 2 === 0 ? ["Mention of RXIL participation", "Supplier finance tie-up noted"] : []
    },
    simulation: {
      required_flag: index % 2 !== 0,
      status: index % 2 !== 0 ? "Simulation required" : "Not required",
      simulated_rating: index % 2 !== 0 ? "BBB-" : null,
      rating_range: index % 2 !== 0 ? "BBB- to BBB" : "External rating available",
      confidence_label: index % 2 !== 0 ? "medium" : null,
      method_used: "backend_black_box",
      notes:
        index % 2 !== 0
          ? ["Mock mode: backend simulation placeholder populated for UI preview."]
          : ["Simulation suppressed because a rating is already available."]
    },
    advisory: {
      notes: [
        "Working capital cycle should be monitored closely over the next two quarters.",
        "Margin protection remains a priority under the current commodity environment."
      ],
      rationale_sections: [
        {
          heading: "Business Position",
          body: "The company retains a meaningful presence in its category with moderate scale and visible working-capital intensity."
        },
        {
          heading: "Financial Risk",
          body: "Leverage is manageable but should be viewed alongside volatility in procurement and inventory cycles."
        }
      ],
      rationale_draft:
        "This mock rationale illustrates how the UI renders narrative output from the backend without computing any new rating logic.",
      processing_notes: ["Mock mode enabled because the API fallback was used."]
    },
    risk_indicator: {
      label: index % 2 === 0 ? "Rated" : "Needs Simulation",
      tone: index % 2 === 0 ? "low" : "medium",
      reasons: [
        index % 2 === 0 ? "External rating available." : "No external rating available in current response.",
        "Working capital remains a visible credit monitor."
      ]
    },
    downloads: {
      excel_url: "#",
      pdf_url: "#",
      word_url: "#"
    },
    ...overrides
  };
}

export const mockCompanies: CompanyDashboardView[] = [
  buildMockCompany("ADM AGRO INDUSTRIES INDIA PRIVATE LIMITED", 0),
  buildMockCompany("GUJARAT AMBUJA EXPORTS LIMITED", 1),
  buildMockCompany("GOYAL PROTEINS LIMITED", 2),
  buildMockCompany("SNEHA FARMS PRIVATE LIMITED", 3),
  buildMockCompany("ABANS ENTERPRISES LIMITED", 4)
];

export function mockCompanyNames(): string[] {
  return mockCompanies.map((company) => company.company_name);
}

export function getMockCompanyByName(name: string): CompanyDashboardView {
  const normalized = name.trim().toLowerCase();
  const existing = mockCompanies.find(
    (company) =>
      company.company_name.toLowerCase() === normalized || (company.company_id || "").toLowerCase() === normalized
  );
  if (existing) {
    return existing;
  }
  return buildMockCompany(name.trim() || "Mock Company", mockCompanies.length + 1, {
    requested_name: name.trim() || "Mock Company"
  });
}

export function buildMockBatch(names: string[]): PortfolioBatchView {
  const companies = names.length ? names.map((name) => getMockCompanyByName(name)) : mockCompanies;
  return {
    batch_id: "mock-batch",
    company_count: companies.length,
    companies,
    batch_excel_url: null,
    batch_zip_url: null,
    workbook_path: null,
    mock_mode: true
  };
}
