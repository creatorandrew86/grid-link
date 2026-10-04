-- =============================================================================
-- Migration 001: Communities Table
-- Purpose: Defines individual energy sharing communities / microgrids.
-- =============================================================================

create table public.communities (
  id          uuid primary key default gen_random_uuid(),
  slug        text not null unique check (slug ~ '^[a-z0-9-]+$'),
  name        text not null check (char_length(trim(name)) between 3 and 100),
  description text default '',
  currency    text not null default 'EUR' check (char_length(currency) = 3),
  timezone    text not null default 'UTC',
  created_at  timestamptz not null default now()
);

create index if not exists idx_communities_slug on public.communities (slug);

alter table public.communities enable row level security;

-- Backend service role has full access
create policy "Service role manages communities"
  on public.communities
  for all
  to service_role
  using (true)
  with check (true);