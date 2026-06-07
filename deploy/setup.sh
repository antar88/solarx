#!/usr/bin/env bash
# One-time deployment for the SolaX dashboard. Run as root on the server.
#
#   sudo DASH_PASSWORD='your-login-password' deploy/setup.sh
#
# Idempotent: safe to re-run. Generates secrets, creates the read-only DB user,
# writes /etc/solarx-api.env, installs systemd units, the nginx site, and TLS.
set -euo pipefail

PROJECT=/var/www/antar88.github.io/apis/solarx
DOMAIN=solar.antarmf.com
API_ENV=/etc/solarx-api.env

if [[ $EUID -ne 0 ]]; then echo "Run as root." >&2; exit 1; fi
if [[ -z "${DASH_PASSWORD:-}" ]]; then
  echo "Set DASH_PASSWORD env var to the dashboard login password." >&2; exit 1
fi

cd "$PROJECT"

echo "==> 1. Rollup table + read-only DB user"
mysql solarx < sql/01_daily_yield.sql
RO_PW="Ro#$(openssl rand -hex 12)Aa1"
sed "s/__PASSWORD__/${RO_PW}/" sql/02_readonly_user.sql | mysql
# Reset password in case the user already existed with a different one.
mysql -e "ALTER USER 'solarx_ro'@'localhost' IDENTIFIED BY '${RO_PW}';"

echo "==> 2. Initial full rollup"
set -a; source /etc/solarx.env; set +a
.venv/bin/python -m jobs.rollup_daily --full

echo "==> 3. Secrets -> ${API_ENV}"
JWT_SECRET="$(openssl rand -hex 32)"
PW_HASH="$(.venv/bin/python -c "from api.auth import hash_password; print(hash_password('${DASH_PASSWORD}'))")"
umask 077
cat > "$API_ENV" <<EOF
SOLARX_RO_DB_USER=solarx_ro
SOLARX_RO_DB_PASSWORD=${RO_PW}
SOLARX_DB=solarx
DB_HOST=localhost
DASH_USERNAME=hantaro88
DASH_PASSWORD_HASH=${PW_HASH}
JWT_SECRET=${JWT_SECRET}
JWT_TTL_HOURS=12
EOF
chown root:www-data "$API_ENV"; chmod 640 "$API_ENV"

echo "==> 4. systemd units"
cp deploy/solarx-api.service deploy/solarx-rollup.service deploy/solarx-rollup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now solarx-api.service
systemctl enable --now solarx-rollup.timer

echo "==> 5. nginx site"
cp deploy/nginx-solar.conf /etc/nginx/sites-available/${DOMAIN}
ln -sf /etc/nginx/sites-available/${DOMAIN} /etc/nginx/sites-enabled/${DOMAIN}
nginx -t && systemctl reload nginx

echo "==> 6. TLS via certbot"
certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos -m antar88@gmail.com --redirect

echo "==> Done. https://${DOMAIN}"
