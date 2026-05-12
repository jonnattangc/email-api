FROM python:3.14-rc-slim

LABEL MAINTAINER="Jonnattan Griffiths"
LABEL VERSION=1.0
LABEL DESCRIPCION="Python Server para leer mail"

ENV TZ='UTC'
ENV USER=jonnattan
ENV HOST_BD=''
ENV USER_BD=''
ENV PASS_BD=''
ENV APPKEY=''
ENV FLASK_APP=app
ENV FLASK_DEBUG=production

RUN addgroup --gid 10101 jonnattan && \
    adduser --home /home/jonnattan --uid 10100 --gid 10101 --disabled-password jonnattan && \
    echo "jonnattan:jonnattan" | chpasswd

WORKDIR /home/jonnattan

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod -R 755 /home/jonnattan && \
    chown -R jonnattan:jonnattan /home/jonnattan

USER jonnattan

WORKDIR /home/jonnattan/app

EXPOSE 8070

CMD ["python", "http-server.py", "8070"]
