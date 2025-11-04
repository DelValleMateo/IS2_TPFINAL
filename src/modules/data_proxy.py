# src/modules/data_proxy.py
import sys
import uuid
import json
from datetime import datetime
from decimal import Decimal
from botocore.exceptions import ClientError
from modules.db_singleton import DatabaseSingleton


class DataProxy:
    def __init__(self):
        try:
            db = DatabaseSingleton()
            self.table_data = db.get_corporate_data_table()
            self.table_log = db.get_corporate_log_table()
            print("DataProxy inicializado.")
        except Exception as e:
            print(
                f"Error fatal al inicializar DataProxy: {e}", file=sys.stderr)
            sys.exit(1)

    def _log_action(self, client_uuid, session_id, action, details=""):
        try:
            item = {
                'id': str(uuid.uuid4()),
                'CPUid': str(client_uuid),
                'sessionid': str(session_id),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'action': action,
                'details': details
            }
            self.table_log.put_item(Item=item)
            print(f"AUDITORÍA: Acción '{action}' registrada.")
        except Exception as e:
            print(f"Error al registrar log: {e}", file=sys.stderr)

    def get_item(self, item_id, client_uuid, session_id):
        self._log_action(client_uuid, session_id, "get", f"ID: {item_id}")
        try:
            response = self.table_data.get_item(Key={'id': item_id})
            return (response['Item'], 200) if 'Item' in response else ({"error": "Missing ID"}, 404)
        except ClientError as e:
            return {"error": e.response['Error']['Message']}, 500

    def set_item(self, item_data, client_uuid, session_id):
        self._log_action(client_uuid, session_id, "set",
                         f"ID: {item_data.get('id')}")
        try:
            item_data_decimal = json.loads(
                json.dumps(item_data), parse_float=Decimal)
            self.table_data.put_item(Item=item_data_decimal)
            return item_data, 200
        except Exception as e:
            return {"error": str(e)}, 400

    def list_items(self, client_uuid, session_id):
        self._log_action(client_uuid, session_id, "list")
        try:
            response = self.table_data.scan()
            return (response['Items'], 200) if 'Items' in response else ([], 200)
        except ClientError as e:
            return {"error": e.response['Error']['Message']}, 500
