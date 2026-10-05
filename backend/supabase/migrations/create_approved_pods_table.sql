-- =============================================================================
-- Migration: Approved PODs Table
-- Purpose: Pre-approves meter identifiers eligible to participate in GridLink.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.approved_pods (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  community_id uuid REFERENCES public.communities(id) ON DELETE CASCADE,
  pod text NOT NULL UNIQUE CHECK (char_length(trim(pod)) BETWEEN 10 AND 36),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Indexes & RLS
CREATE UNIQUE INDEX IF NOT EXISTS idx_approved_pods_upper ON public.approved_pods (upper(trim(pod)));
ALTER TABLE public.approved_pods ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'approved_pods' AND policyname = 'Service role manages approved_pods'
  ) THEN
    CREATE POLICY "Service role manages approved_pods" ON public.approved_pods FOR ALL TO service_role USING (true) WITH CHECK (true);
  END IF;
END
$$;

GRANT ALL ON public.approved_pods TO service_role;
