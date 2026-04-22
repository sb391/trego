alter table public.inquiries
  add column if not exists owner_email text,
  add column if not exists internal_note text,
  add column if not exists last_status_changed_at timestamptz;

update public.inquiries
set last_status_changed_at = coalesce(updated_at, created_at, now())
where last_status_changed_at is null;

create index if not exists inquiries_status_idx on public.inquiries (status);
create index if not exists inquiries_owner_email_idx on public.inquiries (owner_email);
create index if not exists inquiries_last_status_changed_at_idx on public.inquiries (last_status_changed_at desc);

alter table public.export_jobs
  add column if not exists file_format text not null default 'csv',
  add column if not exists row_count integer,
  add column if not exists completed_at timestamptz;

create index if not exists export_jobs_created_at_idx on public.export_jobs (created_at desc);
create index if not exists export_jobs_requested_by_email_idx on public.export_jobs (requested_by_email);
