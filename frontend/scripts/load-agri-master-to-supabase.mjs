import { readFile } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

import nextEnv from "@next/env";
import { createClient } from "@supabase/supabase-js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const seedDir = path.join(projectRoot, "supabase", "seeds", "agri_master");
const { loadEnvConfig } = nextEnv;

// Load the same env chain Next.js uses so local scripts behave like the app.
loadEnvConfig(projectRoot);

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !serviceRoleKey) {
  console.error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  process.exit(1);
}

const supabase = createClient(supabaseUrl, serviceRoleKey, {
  auth: {
    autoRefreshToken: false,
    persistSession: false,
  },
});
const shouldReset = process.argv.includes("--reset");

function chunk(values, size = 100) {
  const output = [];
  for (let index = 0; index < values.length; index += size) {
    output.push(values.slice(index, index + size));
  }
  return output;
}

async function readJson(name) {
  const raw = await readFile(path.join(seedDir, name), "utf-8");
  return JSON.parse(raw);
}

async function replaceChildTable(table, rows, companyIds) {
  if (rows.length === 0 || companyIds.length === 0) {
    return;
  }

  for (const idChunk of chunk(companyIds)) {
    const { error } = await supabase.from(table).delete().in("company_id", idChunk);
    if (error) {
      throw error;
    }
  }

  for (const rowChunk of chunk(rows, 200)) {
    const { error } = await supabase.from(table).insert(rowChunk);
    if (error) {
      throw error;
    }
  }
}

async function resetExistingSeedData() {
  console.log("Reset requested. Clearing existing agri intelligence records before seeding...");

  for (const table of [
    "agri_company_secretaries",
    "agri_simulations",
    "agri_actual_ratings",
    "agri_financial_snapshots",
  ]) {
    const { error } = await supabase.from(table).delete().not("company_id", "is", null);
    if (error) {
      throw error;
    }
  }

  const { error: companiesError } = await supabase.from("agri_companies").delete().not("company_id", "is", null);
  if (companiesError) {
    throw companiesError;
  }

  const { error: importRunsError } = await supabase
    .from("data_import_runs")
    .delete()
    .eq("import_name", "agri_company_master_seed");
  if (importRunsError) {
    throw importRunsError;
  }
}

async function main() {
  const manifest = await readJson("manifest.json");
  const companies = await readJson("agri_companies.json");
  const financials = await readJson("agri_financial_snapshots.json");
  const ratings = await readJson("agri_actual_ratings.json");
  const simulations = await readJson("agri_simulations.json");
  const secretaries = await readJson("agri_company_secretaries.json");

  const companyIds = companies.map((row) => row.company_id);

  if (shouldReset) {
    await resetExistingSeedData();
  }

  const { data: importRun, error: importRunError } = await supabase
    .from("data_import_runs")
    .insert({
      import_name: "agri_company_master_seed",
      source_file: manifest.source_file,
      source_batch: "listed_250cr_profitable",
      source_industry_key: "agri",
      imported_rows: manifest.company_count ?? companies.length,
      metadata: manifest,
    })
    .select("id")
    .single();

  if (importRunError) {
    throw importRunError;
  }

  const companiesWithImportRun = companies.map((row) => ({
    ...row,
    latest_import_run_id: importRun.id,
  }));

  for (const rowChunk of chunk(companiesWithImportRun, 200)) {
    const { error } = await supabase
      .from("agri_companies")
      .upsert(rowChunk, { onConflict: "company_id", ignoreDuplicates: false });
    if (error) {
      throw error;
    }
  }

  await replaceChildTable("agri_financial_snapshots", financials, companyIds);
  await replaceChildTable("agri_actual_ratings", ratings, companyIds);
  await replaceChildTable("agri_simulations", simulations, companyIds);
  await replaceChildTable("agri_company_secretaries", secretaries, companyIds);

  console.log(
    JSON.stringify(
      {
        ok: true,
        reset: shouldReset,
        importRunId: importRun.id,
        companies: companies.length,
        financials: financials.length,
        ratings: ratings.length,
        simulations: simulations.length,
        secretaries: secretaries.length,
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
