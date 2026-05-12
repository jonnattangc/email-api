#!/usr/bin/python

try:
    import logging
    import sys
    import os
    import pymysql.cursors
    from datetime import datetime
    import hashlib
    import json
    import unicodedata
    import threading
    import re
    import requests
    from amodel import AModel

except ImportError:
    logging.error(ImportError)
    print((os.linesep * 2).join(['Error al buscar los modulos:', str(sys.exc_info()[1]), 'Debes Instalarlos para continuar', 'Deteniendo...']))
    sys.exit(-2)

class TrxBcp(AModel):
    llm_api : str = None
    headers : dict = None
    def __init__(self, client: dict = None) :
        super().__init__(client = client)
        
        self.llm_api = os.environ.get('LLM_API_URL', None)

        self.headers = {
            'Authorization' : str(os.environ.get('LLM_AUTH', None)),
            'Content-Type': 'application/json'
        }
    
    def get_data_waza( self, data_msg : dict ) -> dict :
        data = None
        if data_msg :
            try : 
                msg : str = ''
                msg = str(data_msg['name_origen']).strip()
                msg = msg + ' transfire $' + str(data_msg['amount']).strip()
                msg = msg + ' desde ' + str(data_msg['bank_origin']).strip()
                msg = msg + ' el ' + str(data_msg['date_trx']).strip()
                data = {
                    "type": "clear",
                    "data" : {
                        "title_from":"Sistema Automático",
                        "body": str(msg),
                        "name" : "HH:. Tesorero"
                }
            }
            except Exception as e :
                logging.error(f"Error al formatear el mensaje de waza: {str(e)}")
        return data

    def process_mail(self, message: dict = None )  -> dict :
        transfer : dict = None
        sender : str = ''
        subject : str = ''
        id_msg : str = ''
        th : str = '[' + threading.current_thread().name + '-' + str(threading.get_native_id()) + ']'
        try:
            sender = str(message["from"])
            subject = str(message["subject"])
            id_msg = str(message['id'])
            id_msg = id_msg.replace('<-', '').replace('<', '').replace('>', '')
            
            email_message :str = str(message['email'])
            data : bytes = email_message.encode('utf-8')
            md5_hash : str = hashlib.md5(data).hexdigest()
            email_message = unicodedata.normalize('NFC', email_message)

            value = self.get_transaction(id_msg, md5_hash)
            if value != None :
                logging.info(f"{th} ** Ya Existe: " + id_msg )
                return None
                
            logging.info(f"{th} Processing id {id_msg} md5: {md5_hash} from: {sender} subject: {subject}")

            msg : str = 'El siguiente texto es el cuerpo de un correo electronico que contiene información de una transferencia bancaria.'
            msg += email_message
            msg += ' necesito capturar el origen, destino, monto, banco y fecha de la transferencia.'
            msg += ' y que toda la información me la entregues en el formato JSON puro, sin ninguna etiqueta markdown y cunado un campo no exista debe ser nulo. Las claves de JSON siguientes:'
            msg += ' nombre origen como origen_transferencia, banco de origen como banco_de_origen, número de cuenta origen como numero_cuenta_de_origen, monto como monto_transferencia, fecha como fecha,'
            msg += ' hora como hora, codigo de transferecia como codigo_transferencia y comentario como comment'

            data = {
                "type": "clear",
                "data" : {
                    "prompt" : str(msg)
                }
            }
            # logging.info(f"{th} Request: {data}" )
            r = requests.post(self.llm_api,  data = json.dumps(data), headers=self.headers, timeout=30 )
        
            if r.status_code == 200 :
                data_rx = r.json()
                if 'result' in data_rx and data_rx['result'] != None :
                    clean_text = str(data_rx['result']).replace('```json', '').replace('```', '').strip()
                    result : dict = json.loads(clean_text)
                    result['msg_id'] = id_msg
                    result['md5sum'] = md5_hash
                    logging.info(f"{th} Result: {result}" )
                    result['email'] = email_message
                    transfer = self.save_transaction( result ) 

        except Exception as e :
            logging.error("ERROR process_mail() :", e)

        return transfer
    

    