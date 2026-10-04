-- =============================================================================
-- Seed Script: Community, Market Settings & Participants
-- Compatible with migrations 001-004.
-- =============================================================================

WITH upsert_community AS (
  INSERT INTO public.communities (slug, name, description, currency, timezone)
  VALUES (
    'gridlink-community',
    'Comunitatea Energetică GridLink',
    'Comunitate pilot de partajare locală a energiei solare',
    'RON',
    'Europe/Bucharest'
  )
  ON CONFLICT (slug) DO UPDATE
    SET name = EXCLUDED.name
  RETURNING id
),
comm AS (
  SELECT id FROM upsert_community
  UNION
  SELECT id FROM public.communities WHERE slug = 'gridlink-community'
  LIMIT 1
),
insert_settings AS (
  INSERT INTO public.market_settings (community_id, value)
  SELECT 
    comm.id,
    '{"grid_buy": 0.30, "grid_sell": 0.08, "price_weight": 0.60, "transport_fee": 0.015, "buyer_transport_share": 0.50, "solar_yield_factor": 0.75}'::jsonb
  FROM comm
  ON CONFLICT (community_id) DO NOTHING
)
INSERT INTO public.participants (community_id, name, email, password_hash, pod, type, load_kw, solar_kwp)
SELECT
  comm.id,
  p.name,
  p.email,
  p.password_hash,
  p.pod,
  p.type,
  p.load_kw,
  p.solar_kwp
FROM comm, (
  VALUES
    (
      'Bogdan Toma',
      'btoma0513@gmail.com',
      '6b86f12d1cec976a07c871e7e14e7226$23799677507dde5fcec07e4f62f1b7caebc0b4cb73560461c20148625fb39713',
      'RO001BOGDANTOMA01',
      'prosumer',
      3.5000,
      6.0000
    ),
    (
      'Elena Dumitru',
      'elena.dumitru@example.com',
      '94d8cccd38e2820135d11fff088428b9$228211682bdd35c250f4e79270355166dcb9a21b239065fe7e081e4cc00b16d9',
      'RO002ELENADUM0002',
      'consumer',
      2.8000,
      0.0000
    ),
    (
      'Andrei Popescu',
      'andrei.popescu@example.com',
      '94d8cccd38e2820135d11fff088428b9$228211682bdd35c250f4e79270355166dcb9a21b239065fe7e081e4cc00b16d9',
      'RO003ANDREIPOP003',
      'consumer',
      4.2000,
      0.0000
    ),
    (
      'Mihai Ionescu',
      'mihai.ionescu@example.com',
      '94d8cccd38e2820135d11fff088428b9$228211682bdd35c250f4e79270355166dcb9a21b239065fe7e081e4cc00b16d9',
      'RO004MIHAIION0004',
      'prosumer',
      1.5000,
      5.0000
    ),
    (
      'Ioana Radu',
      'ioana.radu@example.com',
      '94d8cccd38e2820135d11fff088428b9$228211682bdd35c250f4e79270355166dcb9a21b239065fe7e081e4cc00b16d9',
      'RO005IOANARAD0005',
      'prosumer',
      2.2000,
      4.2000
    )
) AS p(name, email, password_hash, pod, type, load_kw, solar_kwp)
ON CONFLICT (email) DO UPDATE
  SET
    name = EXCLUDED.name,
    password_hash = EXCLUDED.password_hash,
    pod = EXCLUDED.pod,
    type = EXCLUDED.type,
    load_kw = EXCLUDED.load_kw,
    solar_kwp = EXCLUDED.solar_kwp;
