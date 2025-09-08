#!/usr/bin/python
try:
    import logging
    import sys
    import os
    import time
    import base64
    import uuid
    import imaplib
    import email
    import json
    import pymysql.cursors
    from datetime import datetime
    import threading
    import psutil
    import gc
    from Cipher import Cipher

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
            if path.find('process') >= 0 :    
                util_email : UtilEmail = UtilEmail()
                data = util_email.read_and_save()
                del util_email
                logging.info(name_thread + 'Data read: ' + str(data))
                if data != None :
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

            if path.find('process') >= 0 :    
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

    def read_and_save(self, ) :
            data_rx = {
                "status" : "Ok",
                "transfers" : None
            }
            transfers = []
            try:
                # Conexión al servidor IMAP de Gmail
                imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
                logging.info("Conectando al servidor IMAP...")

                # Iniciar sesi'on
                imap.login(self.user, self.password)
                logging.info("Sesión iniciada con éxito.")

                # Seleccionar la bandeja de entrada (Inbox)
                imap.select("Bancos")
                logging.info("Bandeja de entrada seleccionada.")

                # Buscar todos los correos en la bandeja
                status, messages = imap.search(None, '(FROM "no-reply@tenpo.cl")')
                if str(status) != 'OK':
                    logging.error("Error al buscar correos.")
                    return data_rx
                # El resultado 'messages' es una lista de IDs de correos
                message_ids = messages[0].split()
                logging.info(f"Total de correos encontrados: {len(message_ids)}")
                # Leer los 5 correos más recientes (los IDs vienen en orden ascendente)
                count = 0
                for msg_id in message_ids[-2000:]:
                    status_mail, data = imap.fetch(msg_id, "(RFC822)")
                    #logging.info("=============================== [" + str(msg_id) + "] " + str(status_mail) + " ===============================")
                    if str(status_mail) != 'OK':
                        logging.error(f"Error al obtener el correo con ID {msg_id}.")
                        continue
                    # logging.info("Data:" + str(data))
                    raw_email = data[0][1]
                    email_message = email.message_from_bytes(raw_email)
                    
                    sender : str = ''
                    if email_message["Sender"] != None :
                        sender = str(email_message["Sender"])
                    else :
                        sender = sender + ' ' + str(email_message["From"])
                    subject : str = ''
                    if email_message["Subject"] != None :
                        subject = str(email_message["Subject"])
                    
                    #logging.info("From: " + str(email_message["From"]))
                    if sender.find('no-reply@tenpo.cl') >= 0 and subject.find('Comprobante de transferencia - Tenpo') >= 0 :
                        pos_ini : int = str(email_message).find('>La transferencia de ') + 1
                        pos_end : int = str(email_message).find('fue exitosa') + 11
                        if pos_ini < 0 or pos_end < 0 :
                            continue
                        if pos_end <= pos_ini :
                            continue
                        text : str = str(email_message)[pos_ini:pos_end]
                        pos_ini : int = str(email_message).find('Monto transferencia:')
                        pos_end : int = str(email_message).find('digo de transferencia:') + 35
                        textw : str = str(email_message)[pos_ini:pos_end]
                        text = text + '. ' + textw
                        text = text.replace('\n\n', ',').replace('\n', ',').replace('\t', ' ')
                        text = text.replace(',,', ',').replace(':,', ': ')
                        text = text.replace('N=C2=BA', 'Número').replace(',', ', ').replace('C=C3=B3', 'Có')
                        text = text.replace('=,', ',')
                        #logging.info('[' + str(text) + ']')
                        if text != None :
                            count = count + 1
                            transfer = {
                                "msg_id" : str(email_message["Message-ID"]),
                                "date" : str(email_message["Date"]),
                                "from" : str(sender),
                                "subject" : str(subject)
                            }
                            datos = text.strip().split(', ') 
                            for dato in datos :
                                values = dato.split(': ')
                                if len(values) == 2 :
                                    key : str = values[0].lower().replace('a tu cuenta tenpo fue exitosa. ', '')
                                    key = key.replace('ó', 'o').replace('é', 'e').replace('í', 'i').replace('á', 'a').replace('ú', 'u')
                                    transfer[key] = values[1]
                            transfers.append( transfer )
                            logging.info("Count [" + str(count) + "] " )
                # Cerrar la conexión
                imap.close()
                imap.logout()
                logging.info("Conexión cerrada. Count: " + str(count) )
            except Exception as e:
                logging.error("Ocurrió un error", e)
                transfers = []
                data_rx['status'] = "Error: " + str(e)
            data_rx['transfers'] = transfers
            return data_rx
