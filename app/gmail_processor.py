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
    from datetime import datetime, timedelta
    import threading
    import psutil

except ImportError:
    logging.error(ImportError)
    print((os.linesep * 2).join(['Error al buscar los modulos:', str(sys.exc_info()[1]), 'Debes Instalarlos para continuar', 'Deteniendo...']))
    sys.exit(-2)

ROOT_DIR = os.path.dirname(__file__)

class GMailProcessor():
    client = None
    th : str = None
    def __init__(self, client: None) :
        try:
            self.client = client  
            self.th = '[' + threading.current_thread().name + '-' + str(threading.get_native_id()) + ']'          
        except Exception as e :
            print("ERROR __init__() :", e)
            
    def read_email(self, folder: str = None) :
            transfers : list = []
            meta_info : dict = {}
            if not self.client['meta_filter'] is None :
                meta_info : dict = json.loads(self.client['meta_filter'])
            if folder is None :
                folder = str(meta_info['folder'])
            try:
                # Conexión al servidor IMAP de Gmail
                imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
                logging.info(f"{self.th} Conectando al servidor IMAP...")
                # Iniciar sesi'on
                user : str = self.client['mail_user']
                password : str = self.client['mail_pass']
                logging.info(f"{self.th} Usuario: {user} Contrasena: **********")
                imap.login(user, password)
                
                logging.info(f"{self.th} Sesión iniciada con éxito., Seleccionando bandeja de entrada {folder}...")
                # Seleccionar la bandeja de entrada (Inbox)
                status, data = imap.select(folder)
                if str(status) != 'OK':
                    logging.error(f"{self.th} Error al seleccionar la bandeja de entrada.")
                    return transfers
                days : int = int(meta_info['ago'])
                date_search : datetime = datetime.now() - timedelta(days=days)
                date_search_str : str = date_search.strftime('%d-%b-%Y')
                logging.info(f"{self.th} Busco desde {date_search_str} en {folder} por {days} dias.")

                filter : str = str(meta_info['filter'])
                logging.info(f"{self.th} Filtro Adicional: {filter}")

                status, messages = imap.search(None, filter, '(SINCE "' + date_search_str + '")')
                if str(status) != 'OK':
                    logging.error(f"{self.th} Error al buscar correos.")
                    return transfers
                # El resultado 'messages' es una lista de IDs de correos
                message_ids = messages[0].split()
                logging.info(f"{self.th} Total de correos encontrados: {len(message_ids)}")
                for msg_id in message_ids :
                    status_mail, data = imap.fetch(msg_id, "(RFC822)")
                    if str(status_mail) != 'OK':
                        logging.error(f"{self.th} Error al obtener el correo con ID {msg_id}.")
                        continue
                    raw_email = data[0][1]
                    email_message : email.message.EmailMessage = email.message_from_bytes(raw_email)
                    subject : str = str(email_message['Subject']).lower().strip()
                    transfers.append(
                        {   
                            "subject" : str(subject),
                            "id" : str(email_message["Message-ID"]),
                            "from" : str(email_message['From']),
                            "to" : str(email_message['To']),
                            "date" : str(email_message['Date']),
                            "email" : email_message.as_string(unixfrom=False)
                        }) 
                # Cerrar la conexión
                imap.close()
                imap.logout()
                logging.info(f"{self.th} Cierre de la conexión con el servidor IMAP" )
            except Exception as e:
                logging.error(f"{self.th} Ocurrió un error", e)
                transfers = []
            return transfers
