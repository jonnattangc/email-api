#!/bin/sh

cd /home/jonnattan/source/email-api/cron
echo "[INFO] --------- $(date): Consultando si existen novedades" > ./logs/verify_news.sh.log
curl --location -X POST -H 'Content-Type: application/json' -H 'Authorization: Basic Y2hlY2s6e3t2YXVsdDphdXRob3JpemF0aW9uLXBhc3N3b3JkfX0=' -H 'x-api-key: cbd68de2-0f2c-44ac-9646-707245c48263' -d '{"type":"clear","data":{"name":"Jonna"}}' 'https://api.jonnattan.cl/email/news' >> ./logs/verify_news.sh.log
echo "[INFO] --------- $(date): Consulta realizada" > ./logs/verify_news.sh.log