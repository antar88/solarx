-- Additive migration: bring an existing daily_yield table up to the v2 schema.
-- Safe to run repeatedly (ADD COLUMN IF NOT EXISTS, MariaDB 10.0+).
-- After running, recompute history with: python -m jobs.rollup_daily --full
ALTER TABLE daily_yield
  ADD COLUMN IF NOT EXISTS peak_powerdc       DECIMAL(10,2) NULL AFTER peak_acpower,
  ADD COLUMN IF NOT EXISTS export_kwh         DECIMAL(10,2) NULL AFTER peak_powerdc,
  ADD COLUMN IF NOT EXISTS import_kwh         DECIMAL(10,2) NULL AFTER export_kwh,
  ADD COLUMN IF NOT EXISTS self_consumed_kwh  DECIMAL(10,2) NULL AFTER import_kwh,
  ADD COLUMN IF NOT EXISTS avg_efficiency_pct DECIMAL(5,2)  NULL AFTER self_consumed_kwh,
  ADD COLUMN IF NOT EXISTS uptime_pct         DECIMAL(5,2)  NULL AFTER avg_efficiency_pct;
