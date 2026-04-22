import { promises as fs } from "fs";
import path from "path";

import { NextResponse } from "next/server";

import { getSupabaseAdminClient } from "../../../lib/supabase/admin";
import { isMissingColumnError } from "../../../lib/supabase/schema-compat";
import {
  normalizeCompanyName,
  validateInquirySubmission,
  type InquiryRecord,
} from "../../../lib/inquiries";

const LOCAL_DEV_INQUIRIES = path.join(process.cwd(), "..", "outputs", "dev_inquiries.jsonl");

async function appendLocalInquiry(record: InquiryRecord) {
  await fs.mkdir(path.dirname(LOCAL_DEV_INQUIRIES), { recursive: true });
  await fs.appendFile(LOCAL_DEV_INQUIRIES, `${JSON.stringify(record)}\n`, "utf-8");
}

export async function POST(request: Request) {
  const payload = await request.json().catch(() => null);
  const validation = validateInquirySubmission(payload);

  if (!validation.success) {
    return NextResponse.json({ ok: false, error: validation.error }, { status: 400 });
  }

  const now = new Date().toISOString();
  const record: InquiryRecord = {
    id: crypto.randomUUID(),
    full_name: validation.data.fullName,
    email: validation.data.email,
    company: validation.data.company,
    normalized_company_name: normalizeCompanyName(validation.data.company),
    inquiry_type: validation.data.inquiryType,
    message: validation.data.message,
    phone: validation.data.phone ?? null,
    source_page: validation.data.sourcePage ?? null,
    status: "new",
    owner_email: null,
    internal_note: null,
    last_status_changed_at: now,
    metadata: {
      submission_channel: "website",
    },
    created_at: now,
    updated_at: now,
  };

  if (request.headers.get("x-smoke-test") === "1") {
    return NextResponse.json({
      ok: true,
      mode: "smoke",
      inquiryId: record.id,
      validated: true,
    });
  }

  const client = getSupabaseAdminClient();

  if (!client) {
    if (process.env.NODE_ENV === "production") {
      return NextResponse.json(
        { ok: false, error: "Inquiry persistence is not configured yet." },
        { status: 503 },
      );
    }

    await appendLocalInquiry(record);
    return NextResponse.json({ ok: true, mode: "local-dev", inquiryId: record.id });
  }

  const { error } = await client.from("inquiries").insert(record);

  if (
    error &&
    isMissingColumnError(error, "inquiries", ["owner_email", "internal_note", "last_status_changed_at"])
  ) {
    const legacyRecord = {
      id: record.id,
      full_name: record.full_name,
      email: record.email,
      company: record.company,
      normalized_company_name: record.normalized_company_name,
      inquiry_type: record.inquiry_type,
      message: record.message,
      phone: record.phone,
      source_page: record.source_page,
      status: record.status,
      metadata: record.metadata,
      created_at: record.created_at,
      updated_at: record.updated_at,
    };

    const { error: legacyError } = await client.from("inquiries").insert(legacyRecord);

    if (!legacyError) {
      return NextResponse.json({
        ok: true,
        mode: "supabase-legacy",
        inquiryId: record.id,
        warning: "Inquiry saved, but workflow migration is still pending.",
      });
    }
  }

  if (error) {
    return NextResponse.json({ ok: false, error: error.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true, mode: "supabase", inquiryId: record.id });
}
