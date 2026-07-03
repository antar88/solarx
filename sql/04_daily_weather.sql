-- Daily irradiance/weather rollup from Open-Meteo, keyed by local calendar day.
-- Populated by jobs/fetch_weather.py. Used to compute the Performance Ratio:
--   PR = energy_kwh / (system_kwp * poa_kwh_m2)
-- POA = plane-of-array (tilted) insolation; the reference irradiance is 1 kW/m².
CREATE TABLE IF NOT EXISTS daily_weather (
  day         DATE         NOT NULL PRIMARY KEY,
  poa_kwh_m2  DECIMAL(6,3)     NULL,   -- daily plane-of-array insolation (kWh/m²)
  ghi_kwh_m2  DECIMAL(6,3)     NULL,   -- daily global horizontal insolation (kWh/m²)
  temp_avg    DECIMAL(5,2)     NULL,   -- mean ambient temperature (°C)
  source      VARCHAR(20)  NOT NULL DEFAULT 'open-meteo',
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP
);
