export const INQUIRY_TYPE_OPTIONS = [
  "Credit Rating Simulation",
  "Credit Rating Advisory",
  "TReDS Enablement",
  "Capital & Listing Strategy",
] as const;

export type InquiryType = (typeof INQUIRY_TYPE_OPTIONS)[number];

export type InquirySubmission = {
  fullName: string;
  email: string;
  company: string;
  inquiryType: InquiryType;
  message: string;
  phone?: string | null;
  sourcePage?: string | null;
};

export type InquiryRecord = {
  id: string;
  full_name: string;
  email: string;
  company: string;
  normalized_company_name: string;
  inquiry_type: string;
  message: string;
  phone: string | null;
  source_page: string | null;
  status: string;
  owner_email?: string | null;
  internal_note?: string | null;
  last_status_changed_at?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/i;

function cleanText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function normalizeCompanyName(value: string): string {
  return cleanText(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function validateInquirySubmission(payload: unknown):
  | { success: true; data: InquirySubmission }
  | { success: false; error: string } {
  if (!payload || typeof payload !== "object") {
    return { success: false, error: "Invalid inquiry payload." };
  }

  const fullName = cleanText((payload as Record<string, unknown>).fullName);
  const email = cleanText((payload as Record<string, unknown>).email).toLowerCase();
  const company = cleanText((payload as Record<string, unknown>).company);
  const inquiryType = cleanText((payload as Record<string, unknown>).inquiryType);
  const message = cleanText((payload as Record<string, unknown>).message);
  const phone = cleanText((payload as Record<string, unknown>).phone) || null;
  const sourcePage = cleanText((payload as Record<string, unknown>).sourcePage) || null;

  if (fullName.length < 2) {
    return { success: false, error: "Please enter the contact name." };
  }

  if (!EMAIL_RE.test(email)) {
    return { success: false, error: "Please enter a valid email address." };
  }

  if (company.length < 2) {
    return { success: false, error: "Please enter the company name." };
  }

  if (!INQUIRY_TYPE_OPTIONS.includes(inquiryType as InquiryType)) {
    return { success: false, error: "Please select the service you are interested in." };
  }

  if (message.length < 10) {
    return { success: false, error: "Please add a short note about the requirement." };
  }

  return {
    success: true,
    data: {
      fullName,
      email,
      company,
      inquiryType: inquiryType as InquiryType,
      message,
      phone,
      sourcePage,
    },
  };
}
