# src/modules/db_singleton.py
import boto3
import botocore
import sys


class DatabaseSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            print("Creando nueva instancia de DatabaseSingleton...")
            cls._instance = super(DatabaseSingleton, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):  # Fix para el editor
            self._initialized = False
        if self._initialized:
            return

        print("Inicializando conexión a DynamoDB...")
        try:
            # --- CORRECCIÓN: Se fija la región AWS para consistencia ---
            self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            self.table_corporate_data = self.dynamodb.Table('CorporateData')
            self.table_corporate_log = self.dynamodb.Table('CorporateLog')
            self.table_corporate_data.load()
            self.table_corporate_log.load()
            print("Tablas 'CorporateData' y 'CorporateLog' cargadas.")
            self._initialized = True
        except Exception as e:
            print(
                f"Error fatal al conectar con DynamoDB: {e}", file=sys.stderr)
            sys.exit(1)

    def get_corporate_data_table(self):
        return self.table_corporate_data

    def get_corporate_log_table(self):
        return self.table_corporate_log
