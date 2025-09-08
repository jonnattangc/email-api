FROM python:3.14-rc-slim

LABEL MAINTAINER="Jonnattan Griffiths"
LABEL VERSION=1.0
LABEL DESCRIPCION="Python Server para leer mail"

ENV TZ 'UTC'
ENV HOST_BD ''
ENV USER_BD ''
ENV PASS_BD ''
ENV APPKEY ''
ENV FLASK_APP app
ENV FLASK_DEBUG production


RUN addgroup --gid 10101 jonnattan && \
    adduser --home /home/jonnattan --uid 10100 --gid 10101 --disabled-password jonnattan && \
    echo "jonnattan:jonnattan" | chpasswd
    
RUN echo "Entro a jonnattan:jonnattan" && \
    cd /home/jonnattan && \
    mkdir -p /home/jonnattan/.local/bin && \
    export PATH=$PATH:/home/jonnattan/.local/bin && \
    chmod -R 755 /home/jonnattan && \
    chown -R jonnattan:jonnattan /home/jonnattan

WORKDIR /home/jonnattan

USER jonnattan

COPY . .

RUN pip install -r requirements.txt

WORKDIR /home/jonnattan/app

EXPOSE 8070

CMD [ "python", "http-server.py", "8070"]

