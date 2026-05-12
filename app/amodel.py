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
    from abc import ABC, abstractmethod

except ImportError:
    logging.error(ImportError)
    print((os.linesep * 2).join(['Error al buscar los modulos:', str(sys.exc_info()[1]), 'Debes Instalarlos para continuar', 'Deteniendo...']))
    sys.exit(-2)

ROOT_DIR = os.path.dirname(__file__)

class AModel(ABC):
    db = None
    client : dict = None

    def __init__(self, *args, **kwargs) :
        try:
            if len(args) > 0 or kwargs['client'] is not None:
                self.client = kwargs['client']
            if self.client != None :
                host = os.environ.get('HOST_BD','None')
                user = os.environ.get('USER_BD','None')
                password = os.environ.get('PASS_BD','None')
                port = int(os.environ.get('PORT_BD', 3306))
                eschema = str(os.environ.get('SCHEMA_BD','gral-purpose'))
                self.db = pymysql.connect(host=host, port=port, user=user, password=password, database=eschema, cursorclass=pymysql.cursors.DictCursor)
        except Exception as e :
            logging.exception("__init__() Ocurrió un error")
            self.db = None
    def close(self) :
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
            logging.exception("ERROR evaluate_and_save() :")
        return movements    

    def get_transaction(self, id_msg: str = None, md5: str = None)  -> dict :
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

    def send_waza_message(self, data_msg : dict = None) :
        apikey : str = None
        url : str = os.environ.get('NOTIFICATION_URL', None)
        if self.client != None :
            apikey = str(self.client['api_key'])
        if url != None and apikey != None :
            headers = {
                'x-api-key' : apikey,
                'Content-Type': 'application/json'
            }
            data : dict = self.get_data_waza(data_msg)
            logging.info("Request: " + str(data) )
            try:
                r = requests.post(url,  data = json.dumps(data), headers=headers, timeout=30 )
                logging.info("Response: " + str(r.text) )
            except Exception as e:
                logging.error("Error: " + str(e) )

    @abstractmethod
    def get_data_waza( self, data_msg : dict ) -> dict :
        pass

    def get_tutor_data( self, data_trx : dict ) -> str :
        try:
            rut : str = str(data_trx['rut_origen'])
            rut = rut.replace('-','')
            rut = rut.replace('.','')
            rut = rut.replace(' ','')
            rut = rut.lower()

            sql = """
                WITH BDPadre AS ( 
                    SELECT u.name AS tutor, u.mobile, u.course, ut.name AS rol, u.hijo AS son_id
                    FROM user u 
                    LEFT JOIN user_types ut ON u.user_type = ut.id 
                    WHERE u.user_type != 1 
                    AND LOWER(REPLACE(REPLACE(u.rut, '.', ''), '-', '')) = %s
                ),
                BDHijo AS ( 
                    SELECT us.id AS id, us.name AS son_name 
                    FROM user us 
                    WHERE us.user_type = 1 
                )
                SELECT p.tutor, p.mobile, p.course, p.rol, h.son_name 
                FROM BDPadre p 
                INNER JOIN BDHijo h ON p.son_id = h.id;
                """
            cursor = self.db.cursor()
            cursor.execute(sql, (rut,))
            row = cursor.fetchone()
            logging.info(f"######## Tutor: {row}")
            return row
        except Exception as e :
            logging.error("ERROR get_tutor_data() :", e)
        return None

    def separar(self, text : str) -> str :
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        return re.sub(r'([A-Z])', r' \1', text).strip()

    def save_transaction( self, trx : dict = None ) :
        tmp : str = None
        fecha : str = ''
        hora : str = ''
        trx_code : str = ''
        msg_id : str = ''
        amount : str = ''
        name_origin : str = ''
        rut_origin : str = ''
        client_id : str = str(self.client["id"])

        name_thread = '[' + threading.current_thread().name + '-' + str(threading.get_native_id()) + '] '

        try:
            # logging.info(name_thread + "********* DATOS: " + str(trx))
            data_json = json.dumps(trx)
            try : 
                tmp = trx['origen_transferencia']
                if tmp != None and len(tmp) > 0 :
                    tmp = tmp.replace(',','').strip()
                    tmp = self.separar(tmp.title())
                    name_origin = tmp.title()
                    tmp = None
            except Exception as e :
                name_origin = 'Sin Información'
                tmp = None
            try : 
                tmp = trx['rut_de_origen']
                if tmp != None and len(tmp) > 0 :
                    tmp = tmp.replace(' ','').strip()
                    tmp = tmp.replace(',','').strip()
                    rut_origin = tmp.strip()
                    tmp = None
            except Exception as e :
                rut_origin = 'Sin Información'
                tmp = None
            try : 
                tmp = trx['fecha']
                if tmp != None and len(tmp) > 0 :
                    tmp = tmp.replace(' ','').strip()
                    tmp = tmp.replace('/','-').strip()
                    fecha = tmp
                    tmp = None
            except Exception as e :
                fecha = datetime.now().strftime('%d-%m-%Y') 
                tmp = None
            try : 
                tmp =  trx['hora']
                if tmp != None and len(tmp) > 0 :
                    tmp = tmp.replace(' ','').strip()
                    hora = tmp
                    tmp = None
                else :
                    hora = datetime.now().strftime('%H:%M:%S')
            except Exception as e :
                hora = datetime.now().strftime('%H:%M:%S') 
                tmp = None  
            
            try : 
                tmp =  trx['codigo_transferencia']
                if tmp != None and len(tmp) > 0 :
                    tmp = tmp.replace(' ','').strip()
                    trx_code = tmp
                    tmp = None
            except Exception as e :
                trx_code = 'Sin Información'
                tmp = None  

            try : 
                tmp = trx['msg_id']
                if tmp != None and len(tmp) > 0 :
                    tmp = tmp.replace(' ','').strip()
                    msg_id = tmp.lower()
                    tmp = None
            except Exception as e :
                msg_id = '-1'
                tmp = None

            try : 
                tmp = trx["monto_transferencia"]
                if tmp != None and len(tmp) > 0 :
                    tmp = tmp.replace(' ','').replace('.','').replace(',','').replace('$','').replace(' ','').strip()
                    amount = tmp.lower()
                    tmp = None
            except Exception as e :
                msg_id = '-1'
                tmp = None

            trx_date : str = fecha + ' ' + hora
            date_trx : datetime = datetime.strptime(trx_date, "%d-%m-%Y %H:%M:%S")
            date_now = datetime.now()

            sql = """INSERT INTO Trx (created_at, metadata, name_origen, rut_origen, account_number_origin, bank_origin,
              amount, comment, id_bank_destination, id_msg, id_bank_origin, date_trx, md5sum, client_id) 
              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            
            cursor = self.db.cursor()

            cursor.execute(sql, (date_now.strftime('%Y-%m-%d %H:%M:%S'), data_json, name_origin, rut_origin,trx["numero_cuenta_de_origen"], trx["banco_de_origen"], 
                                 amount, trx["comment"].lower(), trx_code, msg_id, '-1',
                                 date_trx.strftime('%Y-%m-%d %H:%M:%S'), trx["md5sum"].lower(), client_id))
            self.db.commit()
            logging.info(name_thread + 'Datos Guardados')
        except Exception as e :
            logging.error("ERROR save_trasaction() :", e)
            return None
        return self.get_transaction(msg_id, trx["md5sum"])
    @abstractmethod
    def process_mail(self, message: dict = None ) -> dict :
        pass


    