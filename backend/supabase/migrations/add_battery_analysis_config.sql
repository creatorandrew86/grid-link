-- Apply after add_community_battery_planning.sql.
-- The operator/importer supplies sourced battery quotes and explicit technical/financial settings.
-- Null means unavailable; do not seed made-up quotes or measured readings.
alter table public.communities add column if not exists battery_analysis_config jsonb;
