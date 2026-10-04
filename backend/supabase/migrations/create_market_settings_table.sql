-- =============================================================================
-- Migration 003: Market Settings Table
-- Purpose: Isolates tariffs and pricing algorithms per community (1:1 relation).
-- =============================================================================

create table if not exists public.market_settings (
  community_id uuid primary key references public.communities(id) on delete cascade,
  value        jsonb not null,
  updated_at   timestamptz not null default now()
);

-- Enable Row Level Security (RLS)
alter table public.market_settings enable row level security;

-- Policy 1: Backend service role has full access to read and update tariffs
create policy "Service role manages market settings"
  on public.market_settings
  for all
  to service_role
  using (true)
  with check (true);

-- Policy 2: Public read-only access to inspect current market pricing
revoke all on public.market_settings from anon, authenticated;