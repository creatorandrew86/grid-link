create table if not exists public.participants (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(trim(name)) between 2 and 80),
  type text not null check (type in ('consumer', 'prosumer')),
  load_kw numeric(12, 4) not null check (load_kw between 0 and 1000),
  solar_kwp numeric(12, 4) not null default 0 check (solar_kwp between 0 and 1000),
  check ((type = 'consumer' and solar_kwp = 0) or (type = 'prosumer' and solar_kwp > 0))
);
create unique index if not exists participants_name_unique on public.participants (lower(trim(name)));

create table if not exists public.market_settings (
  id integer primary key check (id = 1),
  value jsonb not null
);
insert into public.market_settings (id, value) values (1,
  '{"grid_buy":0.30,"grid_sell":0.08,"price_weight":0.60,"transport_fee":0.015,"buyer_transport_share":0.50,"solar_yield_factor":0.75}'
) on conflict (id) do nothing;

create table if not exists public.clearing_events (
  interval_start timestamptz primary key,
  summary jsonb not null
);

-- Only the server-side secret/service-role key can access these tables.
alter table public.participants enable row level security;
alter table public.market_settings enable row level security;
alter table public.clearing_events enable row level security;
revoke all on public.participants, public.market_settings, public.clearing_events from anon, authenticated;
grant all on public.participants, public.market_settings, public.clearing_events to service_role;
