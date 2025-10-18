#!/usr/bin/python
try:
    import logging
    import sys
    import os
    import pymysql.cursors
    from datetime import datetime
    import hashlib
    import json
    import threading
    import unicodedata
    import re

except ImportError:
    logging.error(ImportError)
    print((os.linesep * 2).join(['Error al buscar los modulos:', str(sys.exc_info()[1]), 'Debes Instalarlos para continuar', 'Deteniendo...']))
    sys.exit(-2)

ROOT_DIR = os.path.dirname(__file__)

class TrxModel():
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
            logging.error("__init__() Ocurrió un error", e)
            self.db = None

        def __del__(self) :
            if self.db != None :
                self.db.close()
    
    def evaluate_and_save(self, mails: list = None) :
        name_thread = '[' + threading.current_thread().name + '-' + str(threading.get_native_id()) + '] '
        movements = []
        try:
            if mails == None :
                return None
            logging.info(name_thread + "Evaluating " + str(len(mails)) + " emails")
            for mail in mails :
                dato = self.process_mail(mail)
                if dato != None :
                    movements.append(dato)
        except Exception as e :
            logging.error("ERROR evaluate_and_save() :", e)
        return movements    
    
    def get_transaction(self, id_msg: str = None, md5: str = None) :
        try:
            sql = """SELECT * FROM Trx where id_msg = %s and md5sum = %s"""
            cursor = self.db.cursor()
            cursor.execute(sql, (id_msg.lower(), md5.lower()))
            results = cursor.fetchall()
            for row in results:
                return row
        except Exception as e :
            logging.error("ERROR get_transactions() :", e)
        return None

    def save_transaction( self, trx : dict = None ) :
        tmp : str = None
        fecha : str = ''
        hora : str = ''
        trx_code : str = ''
        msg_id : str = ''
        amount : str = ''
        name_thread = '[' + threading.current_thread().name + '-' + str(threading.get_native_id()) + '] '
        try:
            cursor = self.db.cursor()
            logging.info(name_thread + "********* DATOS: " + str(trx))
            data_json = json.dumps(trx)
            try : 
                tmp = trx['fecha']
                tmp = tmp.replace(' ','').strip()
                fecha = tmp
                tmp = None
            except Exception as e :
                fecha = datetime.now().strftime('%d-%m-%Y') 
                tmp = None
            try : 
                tmp =  trx['hora']
                tmp = tmp.replace(' ','').strip()
                hora = tmp
                tmp = None
            except Exception as e :
                hora = datetime.now().strftime('%H:%M:%S') 
                tmp = None  
            
            try : 
                tmp =  trx['codigo_transferencia']
                tmp = tmp.replace(' ','').strip()
                trx_code = tmp
                tmp = None
            except Exception as e :
                trx_code = 'Sin Información'
                tmp = None  

            try : 
                tmp = trx['msg_id']
                tmp = tmp.replace(' ','').strip()
                msg_id = tmp.lower()
                tmp = None
            except Exception as e :
                msg_id = '-1'
                tmp = None

            try : 
                tmp = trx["monto_transferencia"]
                tmp = tmp.replace(' ','').replace('.','').replace(',','').replace('$','').replace(' ','').strip()
                amount = tmp.lower()
                tmp = None
            except Exception as e :
                msg_id = '-1'
                tmp = None

            trx_date : str = fecha + ' ' + hora
            date_trx : datetime = datetime.strptime(trx_date, "%d-%m-%Y %H:%M:%S")
            date_now = datetime.now()

            sql = """INSERT INTO Trx (created_at, metadata, name_origen, account_number_origin, bank_origin,
              amount, comment, id_bank_destination, id_msg, id_bank_origin, date_trx, md5sum) 
              VALUES (%s, %s, %s, %s, %s,%s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql, (date_now.strftime('%Y-%m-%d %H:%M:%S'), data_json, trx["origen_transferencia"], trx["numero_cuenta_de_origen"], trx["banco_de_origen"], 
                                 amount, 'Sin comentario', trx_code, msg_id, '-1',
                                 date_trx.strftime('%Y-%m-%d %H:%M:%S'), trx["md5sum"].lower()))
            self.db.commit()
            logging.info(name_thread + 'Datos Guardados')
        except Exception as e :
            logging.error("ERROR save_trasaction() :", e)
            return None
        return self.get_transaction(msg_id, trx["md5sum"])
    def process_mail(self, message: dict = None ) :
        transfer : dict = None
        sender : str = ''
        subject : str = ''
        id_msg : str = ''
        name_thread = '[' + threading.current_thread().name + '-' + str(threading.get_native_id()) + '] '
        try:
            sender = str(message["from"])
            subject = str(message["subject"])
            id_msg = str(message['id'])
            id_msg = id_msg.replace('<-', '').replace('<', '').replace('>', '')
            #logging.info("************** Subject: " + str(subject))
            #logging.info("************** From: " + str(sender))
            if sender.find('no-reply@tenpo.cl') >= 0 and subject.find('comprobante de transferencia') >= 0 :
                email_message :str = str(message['email'])
                data : bytes = email_message.encode('utf-8')
                md5_hash : str = hashlib.md5(data).hexdigest()
                logging.info(name_thread + "processing id: " + id_msg)
                # data_json = json.dumps(email_message)
                value = self.get_transaction(id_msg, md5_hash)
                if value != None :
                    logging.info(name_thread + "** Ya Existe: " + id_msg )
                    return None
                # aca es donde se produce el parser que nos trae problemas por eso limpiamos el email
                # patron_no_imprimible = re.compile(r'[\x00-\x1f\x7f-\x9f\u200b]')
                # email_message = patron_no_imprimible.sub('', email_message)
                email_message = unicodedata.normalize('NFC', email_message)

                # logging.info(name_thread + "** MSG 1: " + email_message )

                pos_ini : int = str(email_message).find('La transferencia de ') 
                pos_end : int = str(email_message).find('Tu saldo puede tardar unos minutos en reflejarse.')
                
                if pos_ini < 0 or pos_end < 0 :
                    logging.info(name_thread + "Error 1 processing id: " + id_msg)
                    return None 
                if pos_end <= pos_ini :
                    logging.info(name_thread + "Error 2 processing id: " + id_msg)
                    return None
                
                text : str = str(email_message)[pos_ini:pos_end]
                text = text.replace('\t', ' ').replace('  ', ' ').replace('\n', ',')
                text = text.replace(',,', ',').replace(':,', ':')
                text = text.replace('N=C2=BA', 'numero').replace('C=C3=B3', 'co')
                text = text.replace('ó', 'o').replace('é', 'e').replace('í', 'i').replace('á', 'a').replace('ú', 'u')
                text = text.replace('$', '').replace('.', '').replace('=', '')
                text = text.lower() 

                # logging.info(name_thread + "** MSG 1: " + text )

                if text != None :
                    transfer = {
                        "msg_id" : str(id_msg),
                        "date" : str(message["date"]),
                        "from" : str(sender),
                        "subject" : str(subject),
                        "md5sum" : str(md5_hash),
                        "text_email" : str(text)
                    }
                    datos = text.strip().split(',') 
                    for dato in datos :
                        values = dato.split(':')
                        if len(values) == 2 :
                            key : str = values[0].replace(' ', '_')
                            transfer[key] = values[1]
                        elif len(values) == 4 and values[0] == 'hora' :
                            key : str = values[0].replace(' ', '_')
                            transfer[key] = values[1] + ':' + values[2] + ':' + values[3]
                        else :
                            key : str = values[0].replace(' ', '_')
                            transfer[key] = ' '.join(values[1:])
                    # se limpian los campos vacios
                    transfer_clean = {
                        key: value
                        for key, value in transfer.items()
                            if value is not None and value != ""
                    }
                    transfer = self.save_transaction( transfer_clean ) 
                else :
                    logging.error(name_thread + "No se pudo obtener el texto del email")
        except Exception as e :
            logging.error("ERROR process_mail() :", e)

        return transfer
    

    