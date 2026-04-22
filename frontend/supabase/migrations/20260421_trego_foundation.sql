create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.admin_users (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique,
  email text not null unique,
  full_name text,
  role text not null default 'admin',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.inquiries (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  company text not null,
  normalized_company_name text not null,
  email text not null,
  phone text,
  inquiry_type text not null,
  message text not null,
  source_page text,
  status text not null default 'new',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint inquiries_status_check check (status in ('new', 'contacted', 'qualified', 'closed')),
  constraint inquiries_type_check check (
    inquiry_type in (
      'Credit Rating Simulation',
      'Credit Rating Advisory',
      'TReDS Enablement',
      'Capital & Listing Strategy'
    )
  )
);

create index if not exists inquiries_normalized_company_idx on public.inquiries (normalized_company_name);
create index if not exists inquiries_created_at_idx on public.inquiries (created_at desc);

create table if not exists public.inquiry_status_events (
  id uuid primary key default gen_random_uuid(),
  inquiry_id uuid not null references public.inquiries(id) on delete cascade,
  previous_status text,
  next_status text not null,
  note text,
  changed_by_email text,
  created_at timestamptz not null default now()
);

create table if not exists public.data_import_runs (
  id uuid primary key default gen_random_uuid(),
  import_name text not null,
  source_file text not null,
  source_batch text,
  source_industry_key text,
  imported_rows integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.agri_companies (
  company_id text primary key,
  company_name text not null,
  normalized_company_name text not null,
  nse_code text,
  bse_code text,
  screener_url text,
  company_workbook_path text,
  source_batch text,
  industry_key text,
  industry_name text,
  industry_group text,
  sub_industry text,
  annual_report_url text,
  annual_report_label text,
  latest_import_run_id uuid references public.data_import_runs(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists agri_companies_normalized_company_idx on public.agri_companies (normalized_company_name);

create table if not exists public.agri_financial_snapshots (
  id bigserial primary key,
  company_id text not null references public.agri_companies(company_id) on delete cascade,
  period text not null,
  revenue_crore numeric,
  net_profit numeric,
  ebitda_margin_pct numeric,
  pat_margin_pct numeric,
  debt_to_equity numeric,
  interest_coverage numeric,
  working_capital_days numeric,
  receivables_days numeric,
  inventory_days numeric,
  networth_crore numeric,
  total_borrowings_crore numeric,
  total_assets_crore numeric,
  current_price numeric,
  market_cap_crore numeric,
  revenue_growth_pct numeric,
  profit_growth_pct numeric,
  is_latest boolean not null default true,
  imported_at timestamptz not null default now(),
  unique (company_id, period)
);

create table if not exists public.agri_actual_ratings (
  id bigserial primary key,
  company_id text not null references public.agri_companies(company_id) on delete cascade,
  rating_status text,
  agency text,
  rating text,
  rating_date date,
  rating_month_year text,
  source text,
  source_url text,
  history_count integer,
  is_latest boolean not null default true,
  imported_at timestamptz not null default now()
);

create index if not exists agri_actual_ratings_company_latest_idx on public.agri_actual_ratings (company_id, is_latest);

create table if not exists public.agri_simulations (
  id bigserial primary key,
  company_id text not null references public.agri_companies(company_id) on delete cascade,
  simulation_required_flag boolean,
  simulated_rating_agency text,
  simulated_rating text,
  calibrated_range text,
  published_range text,
  range_confidence_label text,
  range_usability_label text,
  ca_review_priority text,
  manual_review_required_flag boolean,
  manual_review_reason text,
  is_latest boolean not null default true,
  generated_at timestamptz not null default now()
);

create index if not exists agri_simulations_company_latest_idx on public.agri_simulations (company_id, is_latest);

create table if not exists public.agri_company_secretaries (
  id bigserial primary key,
  company_id text not null references public.agri_companies(company_id) on delete cascade,
  name text,
  contact_details text,
  source_type text,
  source_url text,
  notes text,
  annual_report_url text,
  annual_report_label text,
  is_latest boolean not null default true,
  imported_at timestamptz not null default now()
);

create index if not exists agri_company_secretaries_company_latest_idx on public.agri_company_secretaries (company_id, is_latest);

create table if not exists public.export_jobs (
  id uuid primary key default gen_random_uuid(),
  export_type text not null,
  requested_by_email text,
  status text not null default 'ready',
  filters jsonb not null default '{}'::jsonb,
  output_path text,
  created_at timestamptz not null default now()
);

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'admin_users',
    'inquiries',
    'inquiry_status_events',
    'agri_companies',
    'agri_financial_snapshots',
    'agri_actual_ratings',
    'agri_simulations',
    'agri_company_secretaries',
    'data_import_runs',
    'export_jobs'
  ]
  loop
    execute format('alter table public.%I enable row level security', table_name);
  end loop;
end;
$$;

drop trigger if exists admin_users_set_updated_at on public.admin_users;
create trigger admin_users_set_updated_at
before update on public.admin_users
for each row execute function public.set_updated_at();

drop trigger if exists inquiries_set_updated_at on public.inquiries;
create trigger inquiries_set_updated_at
before update on public.inquiries
for each row execute function public.set_updated_at();

drop trigger if exists agri_companies_set_updated_at on public.agri_companies;
create trigger agri_companies_set_updated_at
before update on public.agri_companies
for each row execute function public.set_updated_at();

create or replace view public.agri_company_master_view as
with latest_financials as (
  select distinct on (company_id)
    company_id,
    period,
    revenue_crore,
    net_profit,
    ebitda_margin_pct,
    pat_margin_pct,
    debt_to_equity,
    interest_coverage,
    working_capital_days,
    receivables_days,
    inventory_days,
    networth_crore,
    total_borrowings_crore,
    total_assets_crore,
    current_price,
    market_cap_crore,
    revenue_growth_pct,
    profit_growth_pct
  from public.agri_financial_snapshots
  order by company_id, is_latest desc, imported_at desc, id desc
),
latest_ratings as (
  select distinct on (company_id)
    company_id,
    rating_status,
    agency,
    rating,
    rating_date,
    rating_month_year,
    source,
    source_url,
    history_count
  from public.agri_actual_ratings
  order by company_id, is_latest desc, imported_at desc, id desc
),
latest_simulations as (
  select distinct on (company_id)
    company_id,
    simulation_required_flag,
    simulated_rating_agency,
    simulated_rating,
    calibrated_range,
    published_range,
    range_confidence_label,
    range_usability_label,
    ca_review_priority,
    manual_review_required_flag,
    manual_review_reason
  from public.agri_simulations
  order by company_id, is_latest desc, generated_at desc, id desc
),
latest_secretaries as (
  select distinct on (company_id)
    company_id,
    name,
    contact_details,
    source_type,
    source_url,
    notes,
    annual_report_url,
    annual_report_label
  from public.agri_company_secretaries
  order by company_id, is_latest desc, imported_at desc, id desc
)
select
  c.company_id,
  c.company_name,
  c.nse_code,
  c.bse_code,
  c.industry_group,
  c.sub_industry,
  c.screener_url,
  c.company_workbook_path,
  f.period,
  f.revenue_crore,
  f.net_profit,
  f.ebitda_margin_pct,
  f.pat_margin_pct,
  f.debt_to_equity,
  f.interest_coverage,
  f.working_capital_days,
  f.receivables_days,
  f.inventory_days,
  f.networth_crore,
  f.total_borrowings_crore,
  f.total_assets_crore,
  f.current_price,
  f.market_cap_crore,
  f.revenue_growth_pct,
  f.profit_growth_pct,
  r.rating_status as latest_cra_rating_status,
  r.agency as latest_cra_rating_agency,
  r.rating as latest_cra_rating,
  r.rating_date as latest_cra_rating_date,
  r.rating_month_year as latest_cra_rating_month_year,
  r.source as latest_cra_rating_source,
  r.source_url as latest_cra_rating_source_url,
  r.history_count as cra_history_count,
  s.name as company_secretary_name,
  s.contact_details as company_secretary_contact_details,
  s.source_type as company_secretary_source_type,
  s.source_url as company_secretary_source_url,
  s.notes as company_secretary_notes,
  coalesce(c.annual_report_url, s.annual_report_url) as annual_report_url,
  coalesce(c.annual_report_label, s.annual_report_label) as annual_report_label,
  sim.simulation_required_flag,
  sim.simulated_rating_agency,
  sim.simulated_rating,
  sim.calibrated_range,
  sim.published_range,
  sim.range_confidence_label,
  sim.range_usability_label,
  sim.ca_review_priority,
  sim.manual_review_required_flag,
  sim.manual_review_reason,
  c.source_batch,
  c.industry_key,
  c.industry_name,
  case
    when c.nse_code is not null or c.bse_code is not null then 'Listed'
    else 'Unlisted'
  end as listed_status,
  c.normalized_company_name
from public.agri_companies c
left join latest_financials f on f.company_id = c.company_id
left join latest_ratings r on r.company_id = c.company_id
left join latest_simulations sim on sim.company_id = c.company_id
left join latest_secretaries s on s.company_id = c.company_id;

create or replace view public.inquiry_agri_dump_view as
select
  i.id as inquiry_id,
  i.created_at as inquiry_created_at,
  i.full_name,
  i.email,
  i.phone,
  i.company,
  i.inquiry_type,
  i.status as inquiry_status,
  i.message,
  i.source_page,
  m.company_id,
  m.industry_name,
  m.listed_status,
  m.revenue_crore,
  m.ebitda_margin_pct,
  m.debt_to_equity,
  m.latest_cra_rating_agency,
  m.latest_cra_rating,
  m.simulated_rating_agency,
  m.simulated_rating,
  m.published_range,
  m.range_confidence_label,
  m.ca_review_priority,
  m.company_secretary_name,
  m.company_secretary_contact_details
from public.inquiries i
left join public.agri_company_master_view m
  on m.normalized_company_name = i.normalized_company_name;
