-- =============================================================================
-- Migration 004: Clearing Events Table
-- Purpose: Immutable history of 15-minute market settlement snapshots.
-- =============================================================================

create table if not exists public.clearing_events (
  community_id   uuid not null references public.communities(id) on delete cascade,
  interval_start timestamptz not null,
  summary        jsonb not null,
  created_at     timestamptz not null default now(),

  -- One immutable snapshot per community per 15-minute interval
  primary key (community_id, interval_start)
);

-- Index for ordering and filtering chronological history by community
create index if not exists idx_clearing_events_timeline 
  on public.clearing_events (community_id, interval_start desc);

-- Enable Row Level Security (RLS)
alter table public.clearing_events enable row level security;

-- Policy 1: Backend service role has write and read access
create policy "Service role manages clearing events"
  on public.clearing_events
  for all
  to service_role
  using (true)
  with check (true);

-- Policy 2: Public read-only access for dashboards and graphs
revoke all on public.clearing_events from anon, authenticated;