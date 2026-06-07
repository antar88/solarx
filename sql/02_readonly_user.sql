-- Read-only DB user for the dashboard API. Least privilege: SELECT only,
-- on just the two tables the API reads. Password is filled in at deploy time.
-- Usage: sed "s/__PASSWORD__/<generated>/" sql/02_readonly_user.sql | mysql
CREATE USER IF NOT EXISTS 'solarx_ro'@'localhost' IDENTIFIED BY '__PASSWORD__';
GRANT SELECT ON solarx.daily_yield   TO 'solarx_ro'@'localhost';
GRANT SELECT ON solarx.inverter_data TO 'solarx_ro'@'localhost';
FLUSH PRIVILEGES;
