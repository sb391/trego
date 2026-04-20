import { buildMockBatch, getMockCompanyByName, mockCompanies, mockCompanyNames } from "./mockData";
import { CompanyDashboardView, PortfolioBatchView } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const FORCE_MOCK = process.env.NEXT_PUBLIC_FORCE_MOCK === "1";

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export async function fetchSampleCompanyNames(): Promise<{ names: string[]; mockMode: boolean }> {
  if (FORCE_MOCK) {
    return { names: mockCompanyNames(), mockMode: true };
  }
  try {
    const payload = await requestJson<{ company_names: string[] }>(`${API_BASE}/api/companies/samples?limit=5`);
    return { names: payload.company_names, mockMode: false };
  } catch {
    return { names: mockCompanyNames(), mockMode: true };
  }
}

export async function fetchCompanyDashboard(identifier: string): Promise<{ company: CompanyDashboardView; mockMode: boolean }> {
  if (FORCE_MOCK) {
    return { company: getMockCompanyByName(identifier), mockMode: true };
  }
  try {
    const company = await requestJson<CompanyDashboardView>(`${API_BASE}/api/company/${encodeURIComponent(identifier)}`);
    return { company, mockMode: false };
  } catch {
    return { company: getMockCompanyByName(identifier), mockMode: true };
  }
}

export async function processPortfolio(companyNames: string[]): Promise<PortfolioBatchView> {
  if (FORCE_MOCK) {
    return buildMockBatch(companyNames);
  }
  try {
    return await requestJson<PortfolioBatchView>(`${API_BASE}/api/ui/portfolio/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company_names: companyNames })
    });
  } catch {
    return buildMockBatch(companyNames);
  }
}

export async function processUpload(file: File): Promise<PortfolioBatchView> {
  if (FORCE_MOCK) {
    return buildMockBatch(mockCompanyNames());
  }
  try {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${API_BASE}/api/ui/portfolio/upload`, {
      method: "POST",
      body: form
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return (await response.json()) as PortfolioBatchView;
  } catch {
    return buildMockBatch(mockCompanyNames());
  }
}

export async function fetchMockSamples(): Promise<CompanyDashboardView[]> {
  if (FORCE_MOCK) {
    return mockCompanies;
  }
  try {
    const payload = await requestJson<{ companies: CompanyDashboardView[]; mock_mode: boolean }>(`${API_BASE}/api/ui/samples?limit=5`);
    return payload.companies;
  } catch {
    return mockCompanies;
  }
}

export function buildAbsoluteUrl(path: string | null | undefined): string | null {
  if (!path || path === "#") {
    return null;
  }
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE}${path}`;
}
