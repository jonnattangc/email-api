#!/bin/sh

cd /home/jonnattan/source/email-api/cron
echo "[INFO] --------- $(date): Consultando si existen novedades" > ./logs/verify_news.sh.log
curl --location -X POST -H 'Content-Type: application/json' -H 'Authorization: Basic __BASIC_VALUE__' -H 'x-api-key: __API_KEY__' -d '{"type":"clear","data":{"name":"Jonna"}}' 'https://api.jonnattan.cl/email/news' >> ./logs/verify_news.sh.log
echo "[INFO] --------- $(date): Consulta realizada" > ./logs/verify_news.sh.log