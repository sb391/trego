import { NextResponse } from "next/server";

import { getInquiryRows, toCsv } from "../../../../../lib/admin/data";
import {
  buildExportFilename,
  buildExportResponse,
  recordExportJob,
  resolveExportFormat,
} from "../../../../../lib/admin/exports";
import { getAuthenticatedAdmin } from "../../../../../lib/admin/auth";

export async function GET(request: Request) {
  const { rows, source } = await getInquiryRows();
  const adminUser = await getAuthenticatedAdmin();
  const format = resolveExportFormat(new URL(request.url).searchParams.get("format"));
  const exportRows = rows.map((row) => ({
    id: row.id,
    full_name: row.full_name,
    email: row.email,
    phone: row.phone,
    company: row.company,
    normalized_company_name: row.normalized_company_name,
    inquiry_type: row.inquiry_type,
    message: row.message,
    source_page: row.source_page,
    status: row.status,
    owner_email: row.owner_email ?? null,
    internal_note: row.internal_note ?? null,
    last_status_changed_at: row.last_status_changed_at ?? null,
    metadata: JSON.stringify(row.metadata ?? {}),
    created_at: row.created_at,
    updated_at: row.updated_at,
  }));
  const body = format === "json" ? JSON.stringify(exportRows, null, 2) : toCsv(exportRows);
  const baseName = `inquiries_${source}`;
  const filename = buildExportFilename(baseName, format);

  await recordExportJob({
    exportType: "inquiries",
    requestedByEmail: adminUser?.email,
    rowCount: exportRows.length,
    fileFormat: format,
    outputPath: `/api/admin/exports/inquiries?format=${format}#${filename}`,
  });

  return buildExportResponse({ body, baseName, format });
}
