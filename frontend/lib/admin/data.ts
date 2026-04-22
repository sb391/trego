import "server-only";

import { promises as fs } from "fs";
import path from "path";

import { getSupabaseAdminClient, hasSupabaseAdminEnv } from "../supabase/admin";
import { normalizeCompanyName, type InquiryRecord } from "../inquiries";

type CellValue = string | number | boolean | null;
type CsvRow = Record<string, CellValue | undefined>;

export type AgriMasterRecord = {
  company_id: string;
  company_name: string;
  normalized_company_name?: string;
  industry_group?: string | null;
  sub_industry?: string | null;
  industry_key?: string | null;
  industry_name?: string | null;
  nse_code?: string | null;
  bse_code?: string | null;
  revenue_crore?: number | null;
  ebitda_margin_pct?: number | null;
  pat_margin_pct?: number | null;
  debt_to_equity?: number | null;
  interest_coverage?: number | null;
  working_capital_days?: number | null;
  receivables_days?: number | null;
  inventory_days?: number | null;
  networth_crore?: number | null;
  total_borrowings_crore?: number | null;
  latest_cra_rating_status?: string | null;
  latest_cra_rating_agency?: string | null;
  latest_cra_rating?: string | null;
  latest_cra_rating_date?: string | null;
  latest_cra_rating_month_year?: string | null;
  latest_cra_rating_source?: string | null;
  latest_cra_rating_source_url?: string | null;
  company_secretary_name?: string | null;
  company_secretary_contact_details?: string | null;
  company_secretary_source_url?: string | null;
  simulation_required_flag?: boolean | null;
  simulated_rating_agency?: string | null;
  simulated_rating?: string | null;
  calibrated_range?: string | null;
  published_range?: string | null;
  range_confidence_label?: string | null;
  range_usability_label?: string | null;
  ca_review_priority?: string | null;
  manual_review_required_flag?: boolean | null;
  manual_review_reason?: string | null;
  source_batch?: string | null;
  annual_report_url?: string | null;
  annual_report_label?: string | null;
  listed_status?: string | null;
  [key: string]: CellValue | undefined;
};

export type AdminSummary = {
  inquiryCount: number;
  agriCompanyCount: number;
  ratedCompanyCount: number;
  simulationRequiredCount: number;
  highPriorityCount: number;
  supabaseMode: boolean;
};

const LOCAL_SEED_DIR = path.join(process.cwd(), "supabase", "seeds", "agri_master");
const MASTER_ROWS_JSON = path.join(LOCAL_SEED_DIR, "agri_company_master_rows.json");
const LOCAL_DEV_INQUIRIES = path.join(process.cwd(), "..", "outputs", "dev_inquiries.jsonl");

async function readJsonFile<T>(filePath: string): Promise<T | null> {
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

async function loadLocalSeedAgriRows(): Promise<AgriMasterRecord[]> {
  const seedRows = await readJsonFile<AgriMasterRecord[]>(MASTER_ROWS_JSON);
  return seedRows ?? [];
}

async function loadSupabaseAgriRows(limit?: number): Promise<AgriMasterRecord[] | null> {
  const client = getSupabaseAdminClient();
  if (!client) {
    return null;
  }

  let query = client.from("agri_company_master_view").select("*").order("company_name");

  if (typeof limit === "number") {
    query = query.limit(limit);
  }

  const { data, error } = await query;
  if (error) {
    return null;
  }

  return (data ?? []) as AgriMasterRecord[];
}

async function loadSupabaseInquiries(limit?: number): Promise<InquiryRecord[] | null> {
  const client = getSupabaseAdminClient();
  if (!client) {
    return null;
  }

  let query = client.from("inquiries").select("*").order("created_at", { ascending: false });

  if (typeof limit === "number") {
    query = query.limit(limit);
  }

  const { data, error } = await query;
  if (error) {
    return null;
  }

  return (data ?? []) as InquiryRecord[];
}

async function loadLocalInquiries(): Promise<InquiryRecord[]> {
  try {
    const raw = await fs.readFile(LOCAL_DEV_INQUIRIES, "utf-8");
    return raw
      .split("\n")
      .filter(Boolean)
      .map((line) => JSON.parse(line) as InquiryRecord)
      .sort((left, right) => right.created_at.localeCompare(left.created_at));
  } catch {
    return [];
  }
}

export async function getAgriMasterRows(limit?: number): Promise<{ rows: AgriMasterRecord[]; source: "supabase" | "seed" }> {
  const supabaseRows = await loadSupabaseAgriRows(limit);
  if (supabaseRows && supabaseRows.length > 0) {
    return { rows: supabaseRows, source: "supabase" };
  }

  const seedRows = await loadLocalSeedAgriRows();
  return {
    rows: typeof limit === "number" ? seedRows.slice(0, limit) : seedRows,
    source: "seed",
  };
}

export async function getInquiryRows(limit?: number): Promise<{ rows: InquiryRecord[]; source: "supabase" | "local" | "none" }> {
  const supabaseRows = await loadSupabaseInquiries(limit);
  if (supabaseRows) {
    return { rows: supabaseRows, source: "supabase" };
  }

  const localRows = await loadLocalInquiries();
  if (localRows.length > 0) {
    return {
      rows: typeof limit === "number" ? localRows.slice(0, limit) : localRows,
      source: "local",
    };
  }

  return { rows: [], source: "none" };
}

export async function getAdminSummary(): Promise<AdminSummary> {
  const [{ rows: inquiries }, { rows: agriRows, source }] = await Promise.all([
    getInquiryRows(),
    getAgriMasterRows(),
  ]);

  const ratedCompanyCount = agriRows.filter(
    (row) => row.latest_cra_rating && row.latest_cra_rating_status?.toLowerCase() !== "not rated",
  ).length;
  const simulationRequiredCount = agriRows.filter((row) => Boolean(row.simulation_required_flag)).length;
  const highPriorityCount = agriRows.filter((row) => row.ca_review_priority?.toLowerCase().includes("high")).length;

  return {
    inquiryCount: inquiries.length,
    agriCompanyCount: agriRows.length,
    ratedCompanyCount,
    simulationRequiredCount,
    highPriorityCount,
    supabaseMode: source === "supabase" && hasSupabaseAdminEnv(),
  };
}

export async function searchAgriCompanies(query: string): Promise<AgriMasterRecord[]> {
  const normalizedQuery = query.trim().toLowerCase();
  const { rows } = await getAgriMasterRows();

  if (!normalizedQuery) {
    return rows.slice(0, 24);
  }

  return rows
    .filter((row) => {
      const candidate = normalizeCompanyName(row.company_name);
      return (
        candidate.includes(normalizedQuery) ||
        (row.industry_name ?? "").toLowerCase().includes(normalizedQuery) ||
        (row.industry_group ?? "").toLowerCase().includes(normalizedQuery) ||
        (row.latest_cra_rating_agency ?? "").toLowerCase().includes(normalizedQuery)
      );
    })
    .slice(0, 24);
}

export async function buildJoinedInquiryDump(): Promise<CsvRow[]> {
  const [{ rows: inquiries }, { rows: agriRows }] = await Promise.all([getInquiryRows(), getAgriMasterRows()]);
  const agriByCompany = new Map(agriRows.map((row) => [normalizeCompanyName(row.company_name), row]));

  return inquiries.map((inquiry) => {
    const company = agriByCompany.get(inquiry.normalized_company_name);
    return {
      inquiry_id: inquiry.id,
      inquiry_created_at: inquiry.created_at,
      full_name: inquiry.full_name,
      email: inquiry.email,
      phone: inquiry.phone,
      company: inquiry.company,
      inquiry_type: inquiry.inquiry_type,
      inquiry_status: inquiry.status,
      inquiry_owner_email: inquiry.owner_email ?? null,
      inquiry_internal_note: inquiry.internal_note ?? null,
      inquiry_last_status_changed_at: inquiry.last_status_changed_at ?? null,
      message: inquiry.message,
      source_page: inquiry.source_page,
      company_id: company?.company_id ?? null,
      industry_name: company?.industry_name ?? null,
      listed_status: company?.listed_status ?? null,
      revenue_crore: company?.revenue_crore ?? null,
      ebitda_margin_pct: company?.ebitda_margin_pct ?? null,
      debt_to_equity: company?.debt_to_equity ?? null,
      latest_cra_rating_agency: company?.latest_cra_rating_agency ?? null,
      latest_cra_rating: company?.latest_cra_rating ?? null,
      latest_cra_rating_status: company?.latest_cra_rating_status ?? null,
      latest_cra_rating_date: company?.latest_cra_rating_date ?? null,
      latest_cra_rating_month_year: company?.latest_cra_rating_month_year ?? null,
      latest_cra_rating_source: company?.latest_cra_rating_source ?? null,
      latest_cra_rating_source_url: company?.latest_cra_rating_source_url ?? null,
      simulated_rating_agency: company?.simulated_rating_agency ?? null,
      simulated_rating: company?.simulated_rating ?? null,
      published_range: company?.published_range ?? null,
      range_confidence_label: company?.range_confidence_label ?? null,
      ca_review_priority: company?.ca_review_priority ?? null,
      company_secretary_name: company?.company_secretary_name ?? null,
      company_secretary_contact_details: company?.company_secretary_contact_details ?? null,
    };
  });
}

export function toCsv(rows: CsvRow[]): string {
  if (rows.length === 0) {
    return "";
  }

  const headers = Array.from(
    rows.reduce((set, row) => {
      Object.keys(row).forEach((key) => set.add(key));
      return set;
    }, new Set<string>()),
  );

  const escapeCell = (value: CellValue) => {
    if (value === null || value === undefined) {
      return "";
    }
    const raw = String(value);
    if (/[",\n]/.test(raw)) {
      return `"${raw.replace(/"/g, '""')}"`;
    }
    return raw;
  };

  const lines = [
    headers.join(","),
    ...rows.map((row) => headers.map((header) => escapeCell(row[header] ?? null)).join(",")),
  ];

  return `${lines.join("\n")}\n`;
}
