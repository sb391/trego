import "server-only";

import { NextResponse } from "next/server";

import { isMissingColumnError } from "../supabase/schema-compat";
import { getSupabaseAdminClient } from "../supabase/admin";

export type ExportFormat = "csv" | "json";

export function resolveExportFormat(value: string | null | undefined): ExportFormat {
  return value === "json" ? "json" : "csv";
}

function buildTimestamp() {
  return new Date().toISOString().replace(/[:T]/g, "-").replace(/\..+$/, "");
}

function extensionFor(format: ExportFormat) {
  return format === "json" ? "json" : "csv";
}

function contentTypeFor(format: ExportFormat) {
  return format === "json" ? "application/json; charset=utf-8" : "text/csv; charset=utf-8";
}

export function buildExportFilename(baseName: string, format: ExportFormat): string {
  return `${baseName}_${buildTimestamp()}.${extensionFor(format)}`;
}

export function buildExportResponse({
  body,
  baseName,
  format,
}: {
  body: string;
  baseName: string;
  format: ExportFormat;
}) {
  const filename = buildExportFilename(baseName, format);

  return new NextResponse(body, {
    headers: {
      "Content-Type": contentTypeFor(format),
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}

export async function recordExportJob({
  exportType,
  requestedByEmail,
  rowCount,
  fileFormat,
  outputPath,
}: {
  exportType: string;
  requestedByEmail?: string | null;
  rowCount: number;
  fileFormat: ExportFormat;
  outputPath: string;
}) {
  const client = getSupabaseAdminClient();
  if (!client) {
    return;
  }

  const exportRecord = {
    export_type: exportType,
    requested_by_email: requestedByEmail ?? null,
    status: "ready",
    filters: {},
    output_path: outputPath,
    file_format: fileFormat,
    row_count: rowCount,
    completed_at: new Date().toISOString(),
  };

  const { error } = await client.from("export_jobs").insert(exportRecord);

  if (
    error &&
    isMissingColumnError(error, "export_jobs", ["file_format", "row_count", "completed_at"])
  ) {
    await client.from("export_jobs").insert({
      export_type: exportType,
      requested_by_email: requestedByEmail ?? null,
      status: "ready",
      filters: {},
      output_path: outputPath,
    });
  }
}
