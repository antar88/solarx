-- Daily rollup of solar generation, derived from inverter_data.
-- One row per local calendar day. Recomputed idempotently by jobs/rollup_daily.py.
-- For an existing deployment, see sql/03_daily_yield_v2.sql (additive migration).
CREATE TABLE IF NOT EXISTS daily_yield (
  day                DATE          NOT NULL PRIMARY KEY,
  energy_kwh         DECIMAL(10,2) NOT NULL,            -- MAX(yieldtoday): PV generated that day
  peak_acpower       DECIMAL(10,2) NOT NULL,            -- MAX(acpower) that day (W)
  peak_powerdc       DECIMAL(10,2)     NULL,            -- MAX(powerdc1) that day (W)
  export_kwh         DECIMAL(10,2)     NULL,            -- grid export that day (delta of feedinenergy)
  import_kwh         DECIMAL(10,2)     NULL,            -- grid import that day (delta of consumeenergy)
  self_consumed_kwh  DECIMAL(10,2)     NULL,            -- generated - exported (PV used on-site)
  avg_efficiency_pct DECIMAL(5,2)      NULL,            -- load-weighted AC/DC efficiency while generating
  uptime_pct         DECIMAL(5,2)      NULL,            -- % of generating samples in Normal status
  samples            INT           NOT NULL,            -- rows aggregated for that day
  updated_at         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                          ON UPDATE CURRENT_TIMESTAMP
);
