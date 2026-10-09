-- Run in Supabase SQL Editor for the Planora Gold project.
-- Private login-attempt counter; never grant access to anon/authenticated.
create table if not exists public.golden_feedback_login_attempts (
  ip_hash text primary key,
  failures integer not null default 0,
  blocked_until timestamptz,
  updated_at timestamptz not null default now()
);
alter table public.golden_feedback_login_attempts enable row level security;
revoke all on public.golden_feedback_login_attempts from anon, authenticated;
-- Only the server-side service role accesses this table.
