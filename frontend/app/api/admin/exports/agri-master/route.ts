import { getAgriMasterRows, toCsv } from "../../../../../lib/admin/data";
import {
  buildExportFilename,
  buildExportResponse,
  recordExportJob,
  resolveExportFormat,
} from "../../../../../lib/admin/exports";
import { getAuthenticatedAdmin } from "../../../../../lib/admin/auth";

export async function GET(request: Request) {
  const { rows, source } = await getAgriMasterRows();
  const adminUser = await getAuthenticatedAdmin();
  const format = resolveExportFormat(new URL(request.url).searchParams.get("format"));
  const body = format === "json" ? JSON.stringify(rows, null, 2) : toCsv(rows);
  const baseName = `agri_master_${source}`;
  const filename = buildExportFilename(baseName, format);

  await recordExportJob({
    exportType: "agri_master",
    requestedByEmail: adminUser?.email,
    rowCount: rows.length,
    fileFormat: format,
    outputPath: `/api/admin/exports/agri-master?format=${format}#${filename}`,
  });

  return buildExportResponse({ body, baseName, format });
}
