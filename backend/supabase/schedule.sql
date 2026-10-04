-- Run only after deploying the clearing function and configuring Vault secrets.
-- Create project_url and gridlink_clearing_token in Supabase Vault first.
create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

select cron.schedule('gridlink-quarter-hour', '*/15 * * * *', $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url') || '/functions/v1/clearing',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-clearing-token', (select decrypted_secret from vault.decrypted_secrets where name = 'gridlink_clearing_token')
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 20000
  );
$$);
