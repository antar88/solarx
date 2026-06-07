-- Daily rollup of solar generation, derived from inverter_data.
-- One row per local calendar day. Recomputed idempotently by jobs/rollup_daily.py.
CREATE TABLE IF NOT EXISTS daily_yield (
  day          DATE          NOT NULL PRIMARY KEY,
  energy_kwh   DECIMAL(10,2) NOT NULL,            -- MAX(yieldtoday) for that local day
  peak_acpower DECIMAL(10,2) NOT NULL,            -- MAX(acpower) that day
  samples      INT           NOT NULL,            -- rows aggregated for that day
  updated_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                       ON UPDATE CURRENT_TIMESTAMP
);
