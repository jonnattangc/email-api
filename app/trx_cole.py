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

class TrxTesoreria(AModel):
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
        if data_msg != None :
            try : 
                mobile : str = None
                tutor_name : str = None
                course : str = 'Tercero'
                rol : str = 'Apoderado'
                alumno : str = None
             
                tutor = self.get_tutor_data( data_msg )

                if tutor != None :
                    mobile = str(tutor['mobile']).strip()
                    tutor_name = str(tutor['tutor']).strip()
                    course = str(tutor['course']).strip()
                    rol = str(tutor['rol']).strip().title()
                    alumno = str(tutor['son_name']).strip().title()
                else :
                    first_name = "Apoderad@"
                    try :
                        logging.info(f"Datos de Transferencia: {data_msg}")
                        first_name = f"{data_msg['name_origen']}".strip()
                    except Exception as e :
                        logging.error(f"Buscando Nombre: {str(e)}")
                    
                    if first_name.find(' ') >= 0 :
                        tutor_name = first_name.split(' ')[0]

                msg : str = f"{rol} "
                if alumno != None and alumno != '' :
                    msg += f"de {alumno} {course}"
                else : 
                    msg += f"del {course}"
                msg += f" se detectó una transferencia de ${self.clp(str(data_msg['amount']).strip())}"
                msg += ' el ' + str(data_msg['date_trx']).strip()
                msg += ' desde ' + str(data_msg['bank_origin']).strip()

                data = {
                    "type": "clear",
                    "data" : {
                        "title_from":"Tesorería Tercero Básico",
                        "body": str(msg),
                        "name" : tutor_name,
                        "phone" : mobile
                    }
                }
            except Exception as e :
                logging.error(f"Error al formatear el mensaje de waza: {str(e)}")
        return data

    def clp(self, valor_texto: str) -> str :
        try:
            numero = int(float(valor_texto))
            valor_formateado = "{:,}".format(numero).replace(",", ".")
            return f"{valor_formateado}"
        except Exception as e :
            logging.error(f"Error al formatear el monto: {str(e)}")
        return valor_texto

    def process_mail(self, message: dict = None ) :
        transfer : dict = None
        sender : str = ''
        subject : str = ''
        id_msg : str = ''
        th = '[' + threading.current_thread().name + '-' + str(threading.get_native_id()) + ']'
        try:
            sender = str(message["from"])
            subject = str(message["subject"]).lower()
            id_msg = str(message['id'])
            id_msg = id_msg.replace('<-', '').replace('<', '').replace('>', '')

            if sender.find('no-reply@tenpo.cl') >= 0 and subject.find('comprobante de transferencia') >= 0 :
                email_message :str = str(message['email'])
                data : bytes = email_message.encode('utf-8')
                md5_hash : str = hashlib.md5(data).hexdigest()

                # data_json = json.dumps(email_message)
                value = self.get_transaction(id_msg, md5_hash)
                if value != None :
                    logging.info(f"{th} ** Ya Existe: {id_msg} ")
                    return None

                email_message = unicodedata.normalize('NFC', email_message)
                logging.info(f"{th} Processing id {id_msg} md5: {md5_hash} from: {sender} subject: {subject}")

                msg : str = 'El siguiente texto es el cuerpo de un correo electronico que contiene información de una transferencia bancaria recibida:'
                msg += email_message
                msg += '. del texto necesito capturar el origen, destino, monto, banco orrigen y fecha de la transferencia. '
                msg += ' y que toda la información me la entregue en el formato JSON puro considerando los tildes y sin ninguna etiqueta markdown y con las claves de JSON siguientes:'
                msg += ' nombre origen como origen_transferencia, el rut como rut_de_origen, banco de origen como banco_de_origen, número de cuenta origen como numero_cuenta_de_origen, monto como monto_transferencia, fecha como fecha,'
                msg += ' hora como hora, codigo de transferecia como codigo_transferencia y comentario como comment'

                data = {
                    "type": "clear",
                    "data" : {
                        "prompt" : str(msg),
                        "assistantType": "Eres un asisente que lee correo electronicos de transferencias recibidas"
                    }
                }
                
                r = requests.post(self.llm_api,  data = json.dumps(data), headers=self.headers, timeout=30 )
        
                if r.status_code == 200 :
                    data_rx = r.json()
                    if not data_rx['result'] is None :
                        clean_text = str(data_rx['result']).replace('```json', '').replace('```', '').strip()
                        
                        logging.info(f"{th} Result: {clean_text}" )
                        
                        result : dict = json.loads(clean_text)
                        result['msg_id'] = id_msg
                        result['md5sum'] = md5_hash
                        
                        logging.info(f"{th} Result: {result}" )

                        result['email'] = email_message
                        transfer = self.save_transaction( result ) 
                else :
                    logging.error(f"{th} Error en llamada a LLM: {r.status_code}")
        except Exception as e :
            logging.error("ERROR process_mail() :", e)

        return transfer
    

    