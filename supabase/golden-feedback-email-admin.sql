-- Run in Supabase SQL Editor. Only a signed-in, verified admin email can read feedback.
alter table public.planora_gold_feedback enable row level security;
grant select on table public.planora_gold_feedback to authenticated;
drop policy if exists "Golden feedback admin read" on public.planora_gold_feedback;
create policy "Golden feedback admin read"
on public.planora_gold_feedback for select to authenticated
using (
  lower(auth.jwt()->>'email') = 'planoracore@gmail.com'
  and (auth.jwt()->>'email_verified')::boolean is true
);
-- Private screenshots: admin can generate short-lived signed URLs.
drop policy if exists "Golden feedback admin screenshot read" on storage.objects;
create policy "Golden feedback admin screenshot read"
on storage.objects for select to authenticated
using (
  bucket_id = 'planora-gold-feedback'
  and lower(auth.jwt()->>'email') = 'planoracore@gmail.com'
  and (auth.jwt()->>'email_verified')::boolean is true
);
