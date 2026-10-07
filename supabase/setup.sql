-- Run once in the Supabase SQL Editor. App access is server-side only.
create table if not exists public.usecta_entries (
  kind text not null check (kind in ('profile','record','template','tender','catalog','supplier')),
  key text not null,
  data jsonb not null,
  primary key (kind, key)
);
alter table public.usecta_entries enable row level security;
revoke all on public.usecta_entries from anon, authenticated;
grant select, insert, update, delete on public.usecta_entries to service_role;
-- No public or authenticated policies: only the server secret can read/write.
insert into storage.buckets (id, name, public)
values ('document-templates', 'document-templates', false)
on conflict (id) do update set public = false;
