import requests
import os
import pymysql

url     = 'https://global.solaxcloud.com/proxyApp/proxy/api/getRealtimeInfo.do'
params  = {
    'tokenId': os.getenv('SOLARX_API_TOKEN'),
    'sn': os.getenv('SOLARX_API_SN')
}

data = None
response = requests.get(url, params=params)
if response.status_code == 200:
    data = response.json()
    print(data)
else:
    print(f"Failed to fetch data: {response.status_code}")
    exit(1)

if not data:
    print(f"Empty data returned from API.")
    exit(1)
elif data.get('success') == False:
    print(f"Api returned an exception: {data.get('exception')}")
    exit(1)

# Database connection parameters
db_host = 'localhost'
db_user = os.getenv('SOLARX_DB_USER')
db_password = os.getenv('SOLARX_DB_PASSWORD')
db_name = os.getenv('SOLARX_DB')

try:
    # Connect to the database
    connection = pymysql.connect(host=db_host, user=db_user, password=db_password, database=db_name)
    cursor = connection.cursor()

    sql = """INSERT INTO inverter_data (
        inverterSN,
        sn,
        acpower,
        yieldtoday,
        yieldtotal,
        feedinpower,
        feedinenergy,
        consumeenergy,
        feedinpowerM2,
        soc,
        peps1,
        peps2,
        peps3,
        inverterType,
        inverterStatus,
        uploadTime,
        batPower,
        powerdc1,
        powerdc2,
        powerdc3,
        powerdc4) 
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

    inverter_data = data.get('result')
    cursor.execute(sql, (
        inverter_data.get('inverterSN'),
        inverter_data.get('sn'),
        inverter_data.get('acpower'),
        inverter_data.get('yieldtoday'),
        inverter_data.get('yieldtotal'),
        inverter_data.get('feedinpower'),
        inverter_data.get('feedinenergy'),
        inverter_data.get('consumeenergy'),
        inverter_data.get('feedinpowerM2'),
        inverter_data.get('soc'),
        inverter_data.get('peps1'),
        inverter_data.get('peps2'),
        inverter_data.get('peps3'),
        inverter_data.get('inverterType'),
        inverter_data.get('inverterStatus'),
        inverter_data.get('uploadTime'),
        inverter_data.get('batPower'),
        inverter_data.get('powerdc1'),
        inverter_data.get('powerdc2'),
        inverter_data.get('powerdc3'),
        inverter_data.get('powerdc4')
    ))

    # Commit the transaction
    connection.commit()

    # Close the connection
    cursor.close()
    connection.close()
    print("Data ingested to the DDBB")
    
except pymysql.Error as e:
    print(f"An error occurred while executing the SQL query: {e}")
    print(sql)
    
