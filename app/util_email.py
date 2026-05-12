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
    from datetime import datetime, timedelta
    import threading
    import psutil
    import gc
    from cipher import Cipher
    from trx_cole import TrxTesoreria
    from trx_logia import TrxBcp
    from amodel import AModel
    from gmail_processor import GMailProcessor

except ImportError:
    logging.error(ImportError)
    print((os.linesep * 2).join(['Error al buscar los modulos:', str(sys.exc_info()[1]), 'Debes Instalarlos para continuar', 'Deteniendo...']))
    sys.exit(-2)

ROOT_DIR = os.path.dirname(__file__)

def message_process( path : str, client : dict ) :
        process = psutil.Process(threading.get_native_id())
        mem_info = process.memory_info() 
        name_thread = '[' + threading.current_thread().name + '-' + str(threading.get_native_id()) + ']'
        logging.info(f"{name_thread} After start thread memory: " + str(mem_info.rss))
        success: bool = False
        try :
            if path.find('news') >= 0 :    
                gmail : GMailProcessor = GMailProcessor(client)
                mails = gmail.read_email()
                del gmail
                news : list = None
                if client['company_name'] == 'Colegio Tesoreria' :
                    processor : AModel = TrxTesoreria(client)
                    news = processor.evaluate_and_save(mails)
                    if news != None :
                        logging.info(f"{name_thread} hay {str(len(news))} nuevas entradas de dinero para notificar" )
                        for new in news :
                            processor.send_waza_message(new)
                    success = True
                    del processor
                elif client['company_name'] == 'Logia BCP' :
                    news : list = None
                    processor : AModel = TrxBcp(client)
                    news = processor.evaluate_and_save(mails)
                    if news != None :
                        logging.info(f"{name_thread} hay {str(len(news))} nuevas entradas de dinero para notificar" )
                        for new in news :
                            processor.send_waza_message(new)
                    success = True
                    del processor
                else :
                    logging.error(f"{name_thread} No se ha configurado el procesador para el cliente {client['company_name']} ")
                    news : list = None  
            else :
                success = False
        except Exception as e :
            logging.error(name_thread + 'Error: ' + str(e))
            success = False
        gc.collect()
        mem_info = process.memory_info() 
        logging.info(f"{name_thread} Before stop thread memory: " + str(mem_info.rss))
        return success

class UtilEmail():
    th = None
    db = None
    user = None
    password = None
    apikey : str = None
    def __init__(self) :
        try:
            host = os.environ.get('HOST_BD','None')
            user = os.environ.get('USER_BD','None')
            password = os.environ.get('PASS_BD','None')
            port = int(os.environ.get('PORT_BD', 3306))
            eschema = str(os.environ.get('SCHEMA_BD','gral-purpose'))
            self.db = pymysql.connect(host=host, port=port, user=user, password=password, database=eschema, cursorclass=pymysql.cursors.DictCursor)
            self.apikey = str(os.environ.get('API_KEY','None'))
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
                        'id'            : str(row['id']),
                        'phone_origin'  : str(row['ws_phone_id']),
                        'bearer_token'  : str(row['ws_bearer_token']),
                        'company_name'  : str(row['company']),
                        'mail_user'     : str(row['mail_user']),
                        'mail_pass'     : str(row['mail_pass']),
                        'meta_filter'     : str(row['meta_filter']),
                        'api_key'       : str(row['apikey'])
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
            if rx_api_key != self.apikey :
                data_response = {"message" : "No autorizado", "data": None}
                http_code  = 401
                logging.error('x-api-key is not valid')
                return  data_response, http_code
            else :
                logging.info(f'x-api-key is valid : {rx_api_key}')
        
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
                clients : str = json_data['clients']
                for cli in clients :
                    client = self.get_client(cli)
                    if client != None :
                        self.th = threading.Thread(target=message_process, args=( path, client ), name='th')
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
