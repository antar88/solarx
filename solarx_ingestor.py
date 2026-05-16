import os
import sys
import logging
import requests
import pymysql
from datetime import datetime

logging.basicConfig(
    filename='/var/log/solarx_ingestor.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

API_URL = 'https://global.solaxcloud.com/api/v2/dataAccess/realtimeInfo/get'
TOKEN   = os.getenv('SOLARX_API_TOKEN')
WIFI_SN = os.getenv('SOLARX_API_SN')

if not TOKEN or not WIFI_SN:
    logging.error('Missing SOLARX_API_TOKEN or SOLARX_API_SN env vars')
    sys.exit(1)

try:
    response = requests.post(
        API_URL,
        headers={'tokenId': TOKEN, 'Content-Type': 'application/json'},
        json={'wifiSn': WIFI_SN},
        timeout=15
    )
    response.raise_for_status()
    data = response.json()
except requests.RequestException as e:
    logging.error(f'API request failed: {e}')
    sys.exit(1)

if not data.get('success'):
    logging.error(f'API error: {data.get("exception")} (code {data.get("code")})')
    sys.exit(1)

r = data.get('result', {})
if not r:
    logging.warning('API returned empty result')
    sys.exit(0)

try:
    connection = pymysql.connect(
        host='localhost',
        user=os.getenv('SOLARX_DB_USER'),
        password=os.getenv('SOLARX_DB_PASSWORD'),
        database=os.getenv('SOLARX_DB'),
        connect_timeout=10
    )
    with connection:
        with connection.cursor() as cursor:
            sql = """
                INSERT IGNORE INTO inverter_data (
                    inverterSN, sn, acpower, yieldtoday, yieldtotal,
                    feedinpower, feedinenergy, consumeenergy, feedinpowerM2,
                    soc, peps1, peps2, peps3, inverterType, inverterStatus,
                    uploadTime, batPower, powerdc1, powerdc2, powerdc3,
                    powerdc4, batStatus, utcDateTime
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
            """
            utc = r.get('utcDateTime')
            if utc:
                utc = datetime.strptime(utc, '%Y-%m-%dT%H:%M:%SZ')

            affected = cursor.execute(sql, (
                r.get('inverterSN'), r.get('sn'), r.get('acpower'),
                r.get('yieldtoday'), r.get('yieldtotal'), r.get('feedinpower'),
                r.get('feedinenergy'), r.get('consumeenergy'), r.get('feedinpowerM2'),
                r.get('soc'), r.get('peps1'), r.get('peps2'), r.get('peps3'),
                r.get('inverterType'), r.get('inverterStatus'), r.get('uploadTime'),
                r.get('batPower'), r.get('powerdc1'), r.get('powerdc2'),
                r.get('powerdc3'), r.get('powerdc4'), r.get('batStatus'), utc
            ))
        connection.commit()

    if affected:
        logging.info(f'Saved: uploadTime={r.get("uploadTime")} acpower={r.get("acpower")}W soc={r.get("soc")}%')
    else:
        logging.info(f'Skipped duplicate: uploadTime={r.get("uploadTime")}')

except pymysql.Error as e:
    logging.error(f'Database error: {e}')
    sys.exit(1)
