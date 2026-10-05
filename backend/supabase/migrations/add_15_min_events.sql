-- =============================================================================
-- Seed Script: Generate 15-Minute Clearing Events for Half a Day (12 Hours)
-- Total intervals: 48 intervals (12 hours * 4 intervals per hour)
-- Target Table: public.clearing_events (community_id, interval_start, summary)
-- =============================================================================

WITH comm AS (
  SELECT id FROM public.communities 
  WHERE slug = 'gridlink-community' 
  LIMIT 1
),
sett AS (
  SELECT 
    coalesce((value->>'grid_buy')::numeric, 0.30) AS grid_buy,
    coalesce((value->>'grid_sell')::numeric, 0.08) AS grid_sell,
    coalesce((value->>'price_weight')::numeric, 0.60) AS price_weight,
    coalesce((value->>'transport_fee')::numeric, 0.015) AS transport_fee,
    coalesce((value->>'buyer_transport_share')::numeric, 0.50) AS buyer_share
  FROM (
    SELECT value FROM public.market_settings 
    WHERE community_id = (SELECT id FROM comm)
    UNION ALL
    SELECT '{"grid_buy": 0.30, "grid_sell": 0.08, "price_weight": 0.60, "transport_fee": 0.015, "buyer_transport_share": 0.50}'::jsonb
    LIMIT 1
  ) s
),
participants_list AS (
  SELECT 
    p.id::text AS id,
    p.name,
    p.email,
    p.pod,
    p.type,
    p.load_kw::numeric AS load_kw,
    p.solar_kwp::numeric AS solar_kwp,
    row_number() OVER (ORDER BY p.created_at) AS rn
  FROM public.participants p
  WHERE p.community_id = (SELECT id FROM comm)
  UNION ALL
  SELECT * FROM (
    VALUES
      ('00000000-0000-0000-0000-000000000001', 'Bogdan Toma', 'btoma0513@gmail.com', 'RO001BOGDANTOMA01', 'prosumer', 3.5000, 6.0000, 1),
      ('00000000-0000-0000-0000-000000000002', 'Elena Dumitru', 'elena.dumitru@example.com', 'RO002ELENADUM0002', 'consumer', 2.8000, 0.0000, 2),
      ('00000000-0000-0000-0000-000000000003', 'Andrei Popescu', 'andrei.popescu@example.com', 'RO003ANDREIPOP003', 'consumer', 4.2000, 0.0000, 3),
      ('00000000-0000-0000-0000-000000000004', 'Mihai Ionescu', 'mihai.ionescu@example.com', 'RO004MIHAIION0004', 'prosumer', 1.5000, 5.0000, 4),
      ('00000000-0000-0000-0000-000000000005', 'Ioana Radu', 'ioana.radu@example.com', 'RO005IOANARAD0005', 'prosumer', 2.2000, 4.2000, 5)
  ) AS fb(id, name, email, pod, type, load_kw, solar_kwp, rn)
  WHERE NOT EXISTS (
    SELECT 1 FROM public.participants WHERE community_id = (SELECT id FROM comm)
  )
),
slots AS (
  -- 48 intervals of 15 minutes = 12 hours (half a day)
  SELECT 
    slot,
    (extract(hour from slot) + extract(minute from slot)/60.0)::numeric AS hour_dec,
    CASE 
      WHEN (extract(hour from slot) + extract(minute from slot)/60.0) BETWEEN 6.0 AND 19.5 
      THEN round(
        greatest(0.0, sin(pi() * ((extract(hour from slot) + extract(minute from slot)/60.0) - 6.0) / 13.5) * 0.82)::numeric, 
        4
      )
      ELSE 0.0000
    END AS solar_factor
  FROM generate_series(
    date_trunc('hour', now()) - interval '12 hours',
    date_trunc('hour', now()) - interval '15 minutes',
    interval '15 minutes'
  ) AS g(slot)
),
participant_slots AS (
  SELECT 
    s.slot,
    s.hour_dec,
    s.solar_factor,
    p.id,
    p.name,
    p.email,
    p.pod,
    p.type,
    p.load_kw,
    p.solar_kwp,
    -- 0.25 hours = 15 minutes per interval
    round(p.load_kw * 0.25 * (0.85 + 0.15 * sin((s.hour_dec + p.rn) * 1.5))::numeric, 4) AS load_kwh,
    round(p.solar_kwp * s.solar_factor * 0.25, 4) AS generation_kwh
  FROM slots s
  CROSS JOIN participants_list p
),
participant_balances AS (
  SELECT 
    ps.*,
    least(ps.load_kwh, ps.generation_kwh) AS self_consumed_kwh,
    greatest(0.0, ps.load_kwh - least(ps.load_kwh, ps.generation_kwh)) AS deficit_kwh,
    greatest(0.0, ps.generation_kwh - least(ps.load_kwh, ps.generation_kwh)) AS surplus_kwh
  FROM participant_slots ps
),
slot_aggregates AS (
  SELECT 
    slot,
    sum(deficit_kwh) AS total_demand,
    sum(surplus_kwh) AS total_supply,
    least(sum(deficit_kwh), sum(surplus_kwh)) AS local_matched
  FROM participant_balances
  GROUP BY slot
),
participant_ledger AS (
  SELECT 
    pb.slot,
    pb.id,
    pb.name,
    pb.email,
    pb.pod,
    pb.type,
    pb.load_kw,
    pb.solar_kwp,
    pb.load_kwh,
    pb.generation_kwh,
    pb.self_consumed_kwh,
    -- P2P matched amounts
    CASE WHEN sa.total_demand > 0 
      THEN round((sa.local_matched * pb.deficit_kwh / sa.total_demand)::numeric, 4) 
      ELSE 0 
    END AS local_bought_kwh,
    CASE WHEN sa.total_supply > 0 
      THEN round((sa.local_matched * pb.surplus_kwh / sa.total_supply)::numeric, 4) 
      ELSE 0 
    END AS local_sold_kwh,
    -- Grid residual flows
    round((pb.deficit_kwh - (CASE WHEN sa.total_demand > 0 THEN sa.local_matched * pb.deficit_kwh / sa.total_demand ELSE 0 END))::numeric, 4) AS grid_import_kwh,
    round((pb.surplus_kwh - (CASE WHEN sa.total_supply > 0 THEN sa.local_matched * pb.surplus_kwh / sa.total_supply ELSE 0 END))::numeric, 4) AS grid_export_kwh,
    -- Financial benchmarks vs P2P
    round((
      pb.deficit_kwh * sett.grid_buy - pb.surplus_kwh * sett.grid_sell
    )::numeric, 4) AS benchmark_bill,
    round((
      (pb.deficit_kwh - (CASE WHEN sa.total_demand > 0 THEN sa.local_matched * pb.deficit_kwh / sa.total_demand ELSE 0 END)) * sett.grid_buy
      + (CASE WHEN sa.total_demand > 0 THEN sa.local_matched * pb.deficit_kwh / sa.total_demand ELSE 0 END) * (sett.grid_sell + sett.price_weight * (sett.grid_buy - sett.grid_sell) + sett.transport_fee * sett.buyer_share)
      - (pb.surplus_kwh - (CASE WHEN sa.total_supply > 0 THEN sa.local_matched * pb.surplus_kwh / sa.total_supply ELSE 0 END)) * sett.grid_sell
      - (CASE WHEN sa.total_supply > 0 THEN sa.local_matched * pb.surplus_kwh / sa.total_supply ELSE 0 END) * (sett.grid_sell + sett.price_weight * (sett.grid_buy - sett.grid_sell) - sett.transport_fee * (1 - sett.buyer_share))
    )::numeric, 4) AS optimized_bill,
    round((
      (CASE WHEN sa.total_demand > 0 THEN sa.local_matched * pb.deficit_kwh / sa.total_demand ELSE 0 END) * (sett.transport_fee * sett.buyer_share)
      + (CASE WHEN sa.total_supply > 0 THEN sa.local_matched * pb.surplus_kwh / sa.total_supply ELSE 0 END) * (sett.transport_fee * (1 - sett.buyer_share))
    )::numeric, 4) AS transport_paid
  FROM participant_balances pb
  JOIN slot_aggregates sa ON sa.slot = pb.slot
  CROSS JOIN sett
),
slot_summaries AS (
  SELECT 
    s.slot AS interval_start,
    (SELECT id FROM comm) AS community_id,
    jsonb_build_object(
      'interval_start', to_char(s.slot at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
      'interval_minutes', 15.0,
      'mode', 'simulation',
      'storage', 'supabase',
      'trade_enabled', true,
      'trade_note', null,
      'rates', jsonb_build_object(
        'clearing_price', round((sett.grid_sell + sett.price_weight * (sett.grid_buy - sett.grid_sell))::numeric, 4),
        'buyer_rate', round((sett.grid_sell + sett.price_weight * (sett.grid_buy - sett.grid_sell) + sett.transport_fee * sett.buyer_share)::numeric, 4),
        'seller_rate', round((sett.grid_sell + sett.price_weight * (sett.grid_buy - sett.grid_sell) - sett.transport_fee * (1 - sett.buyer_share))::numeric, 4),
        'buyer_transport_fee', round((sett.transport_fee * sett.buyer_share)::numeric, 4),
        'seller_transport_fee', round((sett.transport_fee * (1 - sett.buyer_share))::numeric, 4)
      ),
      'settings', jsonb_build_object(
        'grid_buy', sett.grid_buy,
        'grid_sell', sett.grid_sell,
        'price_weight', sett.price_weight,
        'transport_fee', sett.transport_fee,
        'buyer_transport_share', sett.buyer_share,
        'solar_yield_factor', s.solar_factor
      ),
      'totals', jsonb_build_object(
        'load_kwh', round(sum(pl.load_kwh)::numeric, 4),
        'generation_kwh', round(sum(pl.generation_kwh)::numeric, 4),
        'self_consumed_kwh', round(sum(pl.self_consumed_kwh)::numeric, 4),
        'local_traded_kwh', round(sa.local_matched::numeric, 4),
        'grid_import_kwh', round((sa.total_demand - sa.local_matched)::numeric, 4),
        'grid_export_kwh', round((sa.total_supply - sa.local_matched)::numeric, 4),
        'benchmark_bill', round(sum(pl.benchmark_bill)::numeric, 4),
        'optimized_bill', round(sum(pl.optimized_bill)::numeric, 4),
        'benefit', round((sum(pl.benchmark_bill) - sum(pl.optimized_bill))::numeric, 4),
        'transport_collected', round((sa.local_matched * sett.transport_fee)::numeric, 4),
        'local_coverage', CASE WHEN sa.total_demand > 0 THEN round((sa.local_matched / sa.total_demand)::numeric, 4) ELSE 0 END
      ),
      'participants', jsonb_agg(
        jsonb_build_object(
          'id', pl.id,
          'name', pl.name,
          'email', pl.email,
          'pod', pl.pod,
          'type', pl.type,
          'load_kw', pl.load_kw,
          'solar_kwp', pl.solar_kwp,
          'load_kwh', pl.load_kwh,
          'generation_kwh', pl.generation_kwh,
          'self_consumed_kwh', pl.self_consumed_kwh,
          'local_bought_kwh', pl.local_bought_kwh,
          'local_sold_kwh', pl.local_sold_kwh,
          'grid_import_kwh', pl.grid_import_kwh,
          'grid_export_kwh', pl.grid_export_kwh,
          'benchmark_bill', pl.benchmark_bill,
          'optimized_bill', pl.optimized_bill,
          'benefit', round((pl.benchmark_bill - pl.optimized_bill)::numeric, 4),
          'transport_paid', pl.transport_paid
        )
      )
    ) AS summary
  FROM slots s
  JOIN slot_aggregates sa ON sa.slot = s.slot
  JOIN participant_ledger pl ON pl.slot = s.slot
  CROSS JOIN sett
  GROUP BY 
    s.slot, 
    s.solar_factor, 
    sa.local_matched, 
    sa.total_demand, 
    sa.total_supply, 
    sett.grid_buy, 
    sett.grid_sell, 
    sett.price_weight, 
    sett.transport_fee, 
    sett.buyer_share
)
INSERT INTO public.clearing_events (community_id, interval_start, summary)
SELECT 
  community_id,
  interval_start,
  summary
FROM slot_summaries
ON CONFLICT (community_id, interval_start)
DO UPDATE SET summary = EXCLUDED.summary;
