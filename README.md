# Credit Intelligence Platform

Full-stack decision-support platform for Indian corporate credit profiling, starting with agriculture companies.

It combines:

- agriculture company master ingestion
- industry-level Screener export and workbook harvesting for agriculture sub-sectors
- listed/unlisted routing
- Screener workbook reuse for listed companies
- CRA rating-history discovery and parser reuse
- agency-specific rationale research and unrated-company rating simulation
- TReDS proxy detection plus fallback estimation
- rule-based advisory insights
- FastAPI backend APIs
- Next.js analyst UI
- Excel exports for single-company and batch workflows

This is a support tool for CAs and advisors. It is not an official credit rating system.

## What is implemented

### Backend

- `process_company(company_name)` orchestration pipeline
- agriculture workbook ingestion from `data/input/agriculture_companies.xlsx`
- listed/unlisted determination with dataset-first fallback and optional live Screener lookup
- listed-company financial extraction via existing Screener workbook downloads when available
- provider-agnostic financial ingestion for Screener workbooks plus Probe42 PDFs
- unlisted/listed rating discovery via cached rating history, dataset hints, and CRA document parsing
- TReDS proxy search plus model-based estimate fallback
- rule-based advisory note generation
- Excel export for one company or a batch
- caching of processed profiles
- agriculture industry credit-model pipeline for `Agricultural Food & other Products`

### Frontend

- single company input
- bulk CSV/Excel upload
- top-5 sample run
- results table
- listed/unlisted filter
- company detail tabs for Financials, Rating, TReDS, and Advisory
- company detail rationale tab with narrative draft
- single-company Excel download
- single-company Word draft download
- batch Excel download

## Project structure

```text
.
├── frontend/
│   ├── app/
│   ├── components/
│   └── lib/
├── src/
│   ├── credit_intel/
│   │   ├── api.py
│   │   ├── orchestrator.py
│   │   ├── dataset.py
│   │   ├── financial_document_parser.py
│   │   ├── financial_ingestion.py
│   │   ├── probe42_parser.py
│   │   ├── workbook_parser.py
│   │   ├── rating_discovery.py
│   │   ├── rating_repository.py
│   │   ├── treds.py
│   │   ├── advisory.py
│   │   ├── exporter.py
│   │   └── schemas.py
│   ├── parsers/
│   ├── schemas/
│   └── utils/
├── data/
│   ├── input/
│   ├── downloads/
│   └── credit_intel/
│       └── cache/
├── outputs/
│   └── credit_intel/
│       ├── batches/
│       └── samples/
└── tests/
```

## Inputs

- Agriculture company master: `data/input/agriculture_companies.xlsx`
- Existing Screener workbooks: `data/downloads/*.xlsx`
- Provider manifests for local financial documents: `data/input/*.csv`
- Existing parsed rating history: `outputs/credit_rating_history.csv`
- Optional CRA rationale PDFs: `data/input/rating_rationales/`

## Setup

### Python

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

### Frontend

```bash
cd frontend
npm install
```

## Run the backend

```bash
uvicorn src.credit_intel.api:app --reload
```

Backend base URL:

- `http://localhost:8000`

Key endpoints:

- `GET /api/health`
- `GET /api/companies/samples`
- `GET /api/ui/samples`
- `GET /api/company/{company_name}`
- `POST /api/companies/process`
- `POST /api/companies/batch`
- `POST /api/companies/upload`
- `POST /api/ui/portfolio/process`
- `POST /api/ui/portfolio/upload`
- `GET /api/download/company`
- `GET /api/download/company-word`
- `GET /api/ui/reports/company.xlsx`
- `GET /api/ui/reports/company.docx`
- `GET /api/ui/reports/company.pdf`
- `GET /api/download/batch/{batch_id}`
- `POST /api/samples/generate`

## Run the frontend

```bash
cd frontend
npm run dev
```

Frontend URL:

- `http://localhost:3000`

Local UI flow:

- Enter one company name and click `Generate profile`
- Or upload a CSV/Excel file for batch processing
- Review the structured profile in the same UI
- Download Excel, PDF, or Word from the company dashboard detail panel
- Download batch Excel from the portfolio table
- If the backend wrapper is unavailable, the UI falls back to seeded mock profiles

To point the UI at a different backend:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

## Example API calls

Single company:

```bash
curl -X POST http://localhost:8000/api/companies/process \
  -H "Content-Type: application/json" \
  -d '{"company_name":"GUJARAT AMBUJA EXPORTS LIMITED"}'
```

Batch:

```bash
curl -X POST http://localhost:8000/api/companies/batch \
  -H "Content-Type: application/json" \
  -d '{"company_names":["ADM AGRO INDUSTRIES INDIA PRIVATE LIMITED","SNEHA FARMS PRIVATE LIMITED"]}'
```

Generate sample outputs for 5 companies:

```bash
curl -X POST "http://localhost:8000/api/samples/generate?limit=5"
```

## Provider financial ingestion

The simulator can now ingest canonical annual financial tables from both:

- Screener Excel workbooks for listed companies
- Probe42 PDF financial reports for unlisted companies
- Flexible multi-company Excel snapshots from provider exports and ad hoc Excel files

The parser registry is extensible for additional providers such as `scoreme` and `finray`. Provider-style Excel exports can already flow through the flexible Excel parser, and explicit provider overrides such as `scoreme` or `finray` will preserve the source label in the normalized output.

Parse one local document into canonical JSON:

```bash
python3 -m src.cli parse-financial-document \
  --input "/Users/sysadm/Downloads/Financials_TNPRPF_Probe 42 (1).pdf" \
  --output outputs/credit_intel/probe42_sample.json
```

Build a canonical dataset from a manifest:

Manifest columns:

- `company_id`
- `company_name`
- `provider`
- `file_path`
- optional `industry_group`
- optional `sub_industry`
- optional `nse_code`
- optional `bse_code`

Supported manifest provider values today:

- `screener`
- `probe42`
- `generic_excel`
- `scoreme`
- `finray`

Example command:

```bash
python3 -m src.cli build-financial-dataset \
  --manifest data/input/probe42_manifest_sample.csv \
  --output-dir outputs/credit_intel/probe42_dataset_sample
```

Important output files:

- `outputs/credit_intel/probe42_dataset_sample/financial_summary.csv`
- `outputs/credit_intel/probe42_dataset_sample/profit_loss_annual.csv`
- `outputs/credit_intel/probe42_dataset_sample/balance_sheet_annual.csv`
- `outputs/credit_intel/probe42_dataset_sample/cash_flow_annual.csv`
- `outputs/credit_intel/probe42_dataset_sample/ratios_annual.csv`
- `outputs/credit_intel/probe42_dataset_sample/financial_parameters_annual.csv`
- `outputs/credit_intel/probe42_dataset_sample/financial_year_features.csv`
- `outputs/credit_intel/probe42_dataset_sample/latest_financial_features.csv`
- `outputs/credit_intel/probe42_dataset_sample/document_parse_status.csv`

Quality and completeness columns are now included in the normalized outputs:

- `critical_feature_coverage_pct`
- `critical_feature_count_present`
- `critical_feature_count_total`
- `missing_critical_features`
- `simulation_readiness`
- `accuracy_impact_note`

These are especially useful for ad hoc Excel and provider snapshot feeds where some financial drivers may be missing. The model can still run with partial data, but the outputs now tell the user when simulation accuracy is likely to be weaker.

## Agriculture industry credit-model pipeline

This pipeline pulls the Screener export for `Agricultural Food & other Products`, downloads company workbooks, collects rating-history logs, parses external rationale documents, and trains agency-specific simulation models for unrated companies.

Run the full pipeline:

```bash
python3 -m src.cli industry-credit-model \
  --resume \
  --outputs-dir outputs/agri_food_other_products
```

If you need to refresh the Screener industry export:

```bash
python3 -m src.cli industry-credit-model \
  --resume \
  --force-export \
  --outputs-dir outputs/agri_food_other_products
```

Important outputs:

- `outputs/agri_food_other_products/download_status.csv`
- `outputs/agri_food_other_products/credit_rating_history.csv`
- `outputs/agri_food_other_products/simulation_model/financials/financial_year_features.csv`
- `outputs/agri_food_other_products/simulation_model/rationales/agency_rationale_research.md`
- `outputs/agri_food_other_products/simulation_model/training/agency_training_dataset.csv`
- `outputs/agri_food_other_products/simulation_model/models/agency_model_metrics.csv`
- `outputs/agri_food_other_products/simulation_model/simulations/unrated_company_simulations.csv`

## Output files

### Cached profiles

- `data/credit_intel/cache/profiles/*.json`

### Sample outputs

- `outputs/credit_intel/samples/sample_profiles.json`
- `outputs/credit_intel/samples/agriculture_sample_batch.xlsx`

### Batch outputs

- `outputs/credit_intel/batches/*.xlsx`

### Word drafts

- `outputs/credit_intel/word_drafts/*.docx`

### UI report exports

- `outputs/credit_intel/ui_reports/excel/*.xlsx`
- `outputs/credit_intel/ui_reports/pdf/*.pdf`
- `outputs/credit_intel/ui_reports/word/*.docx`
- `outputs/agri_food_other_products/**/*.csv`

### Company workbook structure

Each exported workbook contains:

- `Company Summary`
- `Financials`
- `Rating Details`
- `TReDS Insights`
- `Advisory Notes`

The UI presentation export workbook contains:

- `Summary`
- `Financials`
- `Ratings`
- `TReDS`
- `Simulation`

## Sample companies currently generated

The default top-5 sample run uses:

- `ADM AGRO INDUSTRIES INDIA PRIVATE LIMITED`
- `SNEHA FARMS PRIVATE LIMITED`
- `GUJARAT AMBUJA EXPORTS LIMITED`
- `GOYAL PROTEINS LIMITED`
- `ABANS ENTERPRISES LIMITED`

## Notes and guardrails

- External discovery is cached and rate-limited.
- TReDS output is explicitly marked as proxy-based or model-based.
- Rating simulation is now available through the agriculture industry pipeline and remains clearly labeled as simulated.
- Live Screener lookup is optional and disabled by default unless enabled via environment variable.
- If a listed-company Screener workbook is not already available, the platform falls back to dataset financials.
- The Bloomberg-style frontend and wrapper endpoints are presentation-only and do not compute ratings or scrape data.

## Tests

Run the full suite:

```bash
pytest -q
```

Focused platform tests:

```bash
pytest tests/test_credit_intel_platform.py -q
```
