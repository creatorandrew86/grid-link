-- Apply after the existing community/participant/clearing tables.
-- Meter readings and member decisions are private; only the backend service role accesses them.
begin;

alter table public.communities
  add column if not exists battery_policy text not null default 'undecided'
    check (battery_policy in ('undecided', 'interested', 'declined', 'approved')),
  add column if not exists battery_meter_boundary text not null default 'unverified'
    check (battery_meter_boundary in ('unverified', 'shared_meter', 'separate_meters')),
  add column if not exists battery_accepting_members boolean not null default false,
  add column if not exists network_zone text;

-- Operator-reviewed communities in which this POD can share the battery's billing boundary.
alter table public.approved_pods
  add column if not exists battery_eligible_communities uuid[] not null default '{}';

create table if not exists public.community_meter_intervals (
  community_id uuid not null references public.communities(id) on delete cascade,
  interval_start timestamptz not null,
  summary jsonb not null check (summary->>'mode' = 'measured' and summary->>'currency' = 'RON'),
  created_at timestamptz not null default now(),
  primary key (community_id, interval_start)
);

create table if not exists public.community_battery_interest (
  participant_id uuid primary key references public.participants(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  interested boolean not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.community_transfer_requests (
  id uuid primary key default gen_random_uuid(),
  participant_id uuid not null references public.participants(id) on delete cascade,
  source_community_id uuid not null references public.communities(id) on delete cascade,
  target_community_id uuid not null references public.communities(id) on delete cascade,
  status text not null default 'accepted' check (status = 'accepted'),
  created_at timestamptz not null default now(),
  check (source_community_id <> target_community_id)
);

alter table public.community_meter_intervals enable row level security;
alter table public.community_battery_interest enable row level security;
alter table public.community_transfer_requests enable row level security;
revoke all on public.community_meter_intervals, public.community_battery_interest,
  public.community_transfer_requests from anon, authenticated;
grant all on public.community_meter_intervals, public.community_battery_interest,
  public.community_transfer_requests to service_role;

-- Acceptance is atomic: recheck eligibility under locks, then move membership and its POD approval.
create or replace function public.accept_battery_community_transfer(p_participant_id uuid, p_target_id uuid)
returns jsonb language plpgsql set search_path = public as $$
declare
  member public.participants%rowtype;
  source public.communities%rowtype;
  target public.communities%rowtype;
  transfer_id uuid;
begin
  select * into member from public.participants where id = p_participant_id for update;
  if not found then raise exception 'Member no longer exists'; end if;
  -- Lock both communities in a consistent order to avoid opposing-transfer deadlocks.
  perform id from public.communities where id in (member.community_id, p_target_id) order by id for update;
  select * into source from public.communities where id = member.community_id;
  select * into target from public.communities where id = p_target_id;
  if not found or target.id = source.id
     or source.network_zone is null or trim(source.network_zone) = ''
     or target.network_zone is distinct from source.network_zone
     or target.battery_policy not in ('interested', 'approved')
     or not target.battery_accepting_members or target.battery_meter_boundary <> 'shared_meter'
  then raise exception 'Destination is no longer eligible or accepting members'; end if;
  perform id from public.approved_pods where pod = member.pod and is_active
    and community_id = source.id and target.id = any(battery_eligible_communities) for update;
  if not found then raise exception 'The POD must be approved for both current membership and destination admission'; end if;

  update public.participants set community_id = target.id where id = member.id;
  update public.approved_pods set community_id = target.id where pod = member.pod;
  insert into public.community_battery_interest(participant_id, community_id, interested)
    values (member.id, target.id, true)
    on conflict (participant_id) do update set community_id = excluded.community_id,
      interested = true, updated_at = now();
  insert into public.community_transfer_requests(participant_id, source_community_id, target_community_id, status)
    values (member.id, source.id, target.id, 'accepted') returning id into transfer_id;
  return jsonb_build_object('id', transfer_id, 'status', 'accepted', 'community_id', target.id);
end;
$$;
revoke all on function public.accept_battery_community_transfer(uuid, uuid) from public, anon, authenticated;
grant execute on function public.accept_battery_community_transfer(uuid, uuid) to service_role;

-- Service role bypasses RLS. There are deliberately no browser read/write policies.
commit;

-- An operator sets battery_policy, battery_accepting_members and network_zone.
-- Verify the shared meter before setting battery_meter_boundary = 'shared_meter'.
-- Opening admissions gives advance consent to eligible members in the verified network_zone.
-- Set approved_pods.battery_eligible_communities only after checking the destination meter/settlement boundary.
-- Member acceptance invokes the locked function above. It never collects payments or approves a purchase.
