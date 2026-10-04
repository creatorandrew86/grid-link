-- =============================================================================
-- Migration 002: Participants Table
-- Purpose: Stores consumers and prosumers belonging to a specific community.
-- =============================================================================




-- 1. Create table with password_hash
create table public.participants (
  id            uuid primary key default gen_random_uuid(),
  community_id  uuid not null references public.communities(id) on delete cascade,
  name          text not null check (char_length(trim(name)) between 2 and 80),
  email         text not null check (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
  password_hash text not null check (char_length(password_hash) >= 60),
  pod           text not null check (
    char_length(trim(pod)) between 10 and 36 and
    pod = upper(trim(pod)) and
    pod ~ '^[A-Z0-9]+$'
  ),
  type          text not null check (type in ('consumer', 'prosumer')),
  load_kw       numeric(12, 4) not null check (load_kw between 0 and 1000),
  solar_kwp     numeric(12, 4) not null default 0 check (solar_kwp between 0 and 1000),
  created_at    timestamptz not null default now(),

  constraint chk_participant_solar check (
    (type = 'consumer' and solar_kwp = 0) or
    (type = 'prosumer' and solar_kwp > 0)
  ),
  constraint uq_participant_email unique (email),
  constraint uq_participant_pod unique (pod)
);

-- 2. Indexes
create unique index idx_participants_email_lower on public.participants (lower(trim(email)));
create unique index idx_participants_pod_upper on public.participants (upper(trim(pod)));
create unique index idx_participants_unique_name_per_community on public.participants (community_id, lower(trim(name)));
create index idx_participants_community_id on public.participants (community_id);

-- 3. RLS & Permissions
alter table public.participants enable row level security;
create policy "Service role manages participants" on public.participants for all to service_role using (true) with check (true);
revoke all on public.participants from anon, authenticated;
grant all on public.participants to service_role;