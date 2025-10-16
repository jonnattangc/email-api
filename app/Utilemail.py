#!/usr/bin/python
try:
    import logging
    import sys
    import os
    import time
    import base64
    import uuid
    import requests
    import imaplib
    import email
    import json
    import pymysql.cursors
    from datetime import datetime
    import threading
    import psutil
    import gc
    from Cipher import Cipher
    from TrxModel import TrxModel

except ImportError:
    logging.error(ImportError)
    print((os.linesep * 2).join(['Error al buscar los modulos:', str(sys.exc_info()[1]), 'Debes Instalarlos para continuar', 'Deteniendo...']))
    sys.exit(-2)

ROOT_DIR = os.path.dirname(__file__)

def message_process( json_data, path : str, client ) :
        process = psutil.Process(threading.get_native_id())
        mem_info = process.memory_info() 
        name_thread = '[' + threading.current_thread().name + '-' + str(threading.get_native_id()) + '] '
        logging.info(name_thread + "After start thread memory: " + str(mem_info.rss))
        success: bool = False
        try :
            if path.find('news') >= 0 :    
                util_email : UtilEmail = UtilEmail()
                mails = util_email.read_email('Bancos')
                del util_email
                processor = TrxModel()
                news : list = processor.evaluate_and_save(mails)
                del processor
                logging.info(name_thread + 'A Notificar: ' + str(len(news)) + ' Entradas de dinero')
                if news != None :
                    for new in news :
                        notify_wathsapp(new)
                    success = True
            else :
                success = False
        except Exception as e :
            logging.error(name_thread + 'Error: ' + str(e))
            success = False
        
        gc.collect()

        mem_info = process.memory_info() 
        logging.info(name_thread + "Before stop thread memory: " + str(mem_info.rss))

        if success :
            logging.info(name_thread + 'ha terminado con exito...')
        else :
            logging.error(name_thread + 'ha terminado con falla...')

        return success

def notify_wathsapp( data_mail : dict ) :
    url = os.environ.get('NOTIFICATION_URL','None')
    apikey = os.environ.get('NOTIFICATION_APIKEY','None')
    phone = os.environ.get('PHONE','None')
    if url != None and apikey != None :
        headers = {
            'x-api-key' : apikey,
        }

        msg : str = ''
        try : 
            msg = data_mail['text_email']
            msg = msg.replace(' ','').strip()
        except Exception as e :
            msg = 'sin informción adicional'

        data = {
            "type": "clear",
            "to" : phone,
            "subject":"Tesorero 2°A",
            "body": msg
        }

        try:
            r = requests.post(url, json=data, headers=headers, hooks=None, timeout=5 )
            logging.info("Response: " + str(r.text) )
        except Exception as e:
            logging.error("Error: " + str(e) )

class UtilEmail():
    th = None
    db = None
    user = None
    password = None
    def __init__(self) :
        try:
            host = os.environ.get('HOST_BD','None')
            user = os.environ.get('USER_BD','None')
            password = os.environ.get('PASS_BD','None')
            port = int(os.environ.get('PORT_BD', 3306))
            eschema = str(os.environ.get('SCHEMA_BD','gral-purpose'))
            self.db = pymysql.connect(host=host, port=port, user=user, password=password, database=eschema, cursorclass=pymysql.cursors.DictCursor)
            self.user = str(os.environ.get('EMAIL_ACCOUNT','None'))
            mypass = str(os.environ.get('EMAIL_PASS','None'))
            self.password = mypass.replace('-', ' ')
        except Exception as e :
            print("ERROR __init__() :", e)
            self.db = None

    def __del__(self) :
        if self.db != None :
            self.db.close()
    
    def get_client(self, apikey: str) :
        client = None
        try :
            if self.db != None :
                cursor = self.db.cursor()
                sql = """select * from clients where apikey = %s"""
                cursor.execute(sql, (apikey))
                results = cursor.fetchall()
                for row in results:
                    client = {
                        'phone_origin' : str(row['ws_phone_id']),
                        'bearer_token' : str(row['ws_bearer_token']),
                        'company_name' : str(row['company']),
                        'mail_user' : str(row['mail_user']),
                        'password' : str(row['mail_pass']),
                    }
                    logging.info("Client found: " + str(client['company_name']) )   
        except Exception as e:
            print("ERROR BD get_client():", e)
        return client

    def request_process(self, request, subpath: str ) :
        logging.info("=============================== INIT ===============================" )
        logging.info("Reciv " + str(request.method) + " Acción: " + str(subpath) )
        logging.info("Reciv Data: " + str(request.data) )
        logging.info("Reciv Header : " + str(request.headers) )

        data_response = {"message" : "Servicio ejecutado exitosamente", "data": None}
        http_code  = 200
        client = None

        # evalua pai key inmediatamente
        rx_api_key: str = request.headers.get('x-api-key')
        if rx_api_key == None :
            logging.error('x-api-key no found')
            data_response = {"message" : "No autorizado", "data": None}
            http_code  = 409
            return  data_response, http_code
        else :
            logging.info(f'x-api-key found : {rx_api_key}')
            client = self.get_client(rx_api_key)
            if client == None :
                data_response = {"message" : "No autorizado", "data": None}
                http_code  = 401
                logging.error('x-api-key is not valid')
                return  data_response, http_code
            else :
                logging.info(f'Client found: {client}' )
        path : str = None 
        if subpath != None : 
            path = subpath.lower().strip()

        if request.method == 'POST' :
            request_data = request.get_json()
            json_data = None
            request_type = None
            data_rx = None
            try :
                request_type = request_data['type']
            except Exception as e :
                request_type = None
            try :
                data_rx = request_data['data']
            except Exception as e :
                data_rx = None
            if request_type != None :
                # encrypted or inclear
                if data_rx != None and str(request_type) == 'encrypted' :
                    cipher = Cipher()
                    data_cipher = str(data_rx)
                    logging.info('Data Encrypt: ' + str(data_cipher) )
                    data_clear = cipher.aes_decrypt(data_cipher)
                    logging.info('Data EnClaro: ' + str(data_clear) )
                    json_data = json.dumps(data_clear)
                    del cipher
                else: 
                    json_data = data_rx
            else: 
                    json_data = data_rx

            if path.find('news') >= 0 :    
                self.th = threading.Thread(target=message_process, args=( json_data, path, client ), name='th')
                self.th.start()
            elif path.find('search') >= 0 :
                data_response = {"message" : "No implementado", "data": None}
                http_code = 404
            else :
                data_response = {"message" : "Servicio no encontrado", "data": None}
                http_code = 404
        elif request.method == 'GET' :
            if path.find('read') >= 0 :
                data_response = {"message" : "No implementado", "data": None}
                http_code = 404
        else :
            http_code = 404
        return  data_response, http_code

    def read_email(self, filter: str) :
            transfers : list = []
            try:
                # Conexión al servidor IMAP de Gmail
                imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
                logging.info("Conectando al servidor IMAP...")
                # Iniciar sesi'on
                imap.login(self.user, self.password)
                logging.info("Sesión iniciada con éxito.")
                # Seleccionar la bandeja de entrada (Inbox)
                imap.select(filter)
                logging.info("Bandeja de entrada seleccionada.")
                # Buscar todos los correos en la bandeja
                status, messages = imap.search(None, '(FROM "no-reply@tenpo.cl")')
                if str(status) != 'OK':
                    logging.error("Error al buscar correos.")
                    return transfers
                # El resultado 'messages' es una lista de IDs de correos
                message_ids = messages[0].split()
                logging.info(f"Total de correos encontrados: {len(message_ids)}")
                count = 0
                for msg_id in message_ids :
                    status_mail, data = imap.fetch(msg_id, "(RFC822)")
                    if str(status_mail) != 'OK':
                        logging.error(f"Error al obtener el correo con ID {msg_id}.")
                        continue
                    raw_email = data[0][1]
                    email_message : email.message.EmailMessage = email.message_from_bytes(raw_email)
                    if str(email_message['Subject']).find('Comprobante de transferencia') >= 0 :
                        transfers.append(
                            {   
                                "subject" : str(email_message['Subject']),
                                "id" : str(email_message["Message-ID"]),
                                "from" : str(email_message['From']),
                                "to" : str(email_message['To']),
                                "date" : str(email_message['Date']),
                                "email" : email_message.as_string()
                            })
                        count = count + 1
                # Cerrar la conexión
                imap.close()
                imap.logout()
                logging.info("Conexión cerrada. Procesados: " + str(count) )
            except Exception as e:
                logging.error("Ocurrió un error", e)
                transfers = []
            return transfers
