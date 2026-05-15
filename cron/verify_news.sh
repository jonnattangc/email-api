#!/bin/sh

cd /home/jonnattan/source/email-api/cron
echo "[INFO] --------- $(date): Consultando si existen novedades" > ./logs/verify_news.sh.log
curl --location -X POST -H 'Content-Type: application/json' -H 'Authorization: Basic Y2hlY2s6e3t2YXVsdDphdXRob3JpemF0aW9uLXBhc3N3b3JkfX0=' -H 'x-api-key: 3c1b6bfa-cc52-4d94-ba8e-e1d1496878f3' -d '{"type":"clear","data":{"clients":["8666d3d6-c254-4fbf-8566-29ec69da19bc","cb158fdd-0db2-48bc-b558-9acf95abda35"]}}' 'https://api.jonnattan.cl/email/news' >> ./logs/verify_news.sh.log