import boto3
from botocore.exceptions import ClientError
import sys
import json
from decimal import Decimal
import time

# --- CONFIGURACIÓN ---
AWS_REGION = 'us-east-1'  # ¡Asegúrese de que esta región sea la correcta!
TABLE_NAME = 'CorporateLog'

# Clase para manejar la conversión de Decimal a string en JSON


class DecimalEncoder(json.JSONEncoder):
    """Convierte tipos de datos de DynamoDB (Decimal) a string para la salida JSON."""

    def default(self, obj):
        return str(obj) if isinstance(obj, Decimal) else super(DecimalEncoder, self).default(obj)

# --- LÓGICA DE AUDITORÍA Y ORDENAMIENTO ---


def safe_timestamp_key(item):
    """
    Función de clave de ordenamiento SEGURA.
    Garantiza que solo las cadenas que parecen fechas (ej. '2025-...')
    se usen para ordenar. Los valores corruptos se asignan a una fecha antigua.
    """
    # Usamos .get() para asegurarnos de que el script no falle si falta el campo 'timestamp'.
    timestamp_str = str(item.get('timestamp', '0000-01-01 00:00:00'))

    # Verificamos si la cadena de tiempo empieza con '20' (asumimos año 20xx o 202x).
    if timestamp_str.startswith('20'):
        return timestamp_str

    # Si la cadena no parece una fecha (ej. es un UUID o un valor corrupto),
    # le asignamos una fecha muy antigua.
    return '0000-01-01 00:00:00'


def get_total_count(table):
    """Obtiene el número total de registros de forma eficiente."""
    # Nota: Este conteo es eventualmente consistente, pero es la forma más rápida de obtener el total.
    response = table.scan(Select='COUNT')
    return response.get('Count', 0)


def get_latest_log(table):
    """
    Obtiene el registro más reciente buscando en toda la tabla (Scan Completo).
    Usa la función de ordenamiento condicional para ignorar datos corruptos.
    """
    # Hacemos un Scan Completo para garantizar encontrar el registro más reciente.
    response = table.scan(
        Select='ALL_ATTRIBUTES',
        ConsistentRead=True
    )

    items = response.get('Items', [])
    if not items:
        return None

    # Ordenamos usando la clave segura, forzando que los corruptos vayan al final.
    items.sort(key=safe_timestamp_key, reverse=True)

    # El primer elemento después de ordenar es el más reciente (después de descartar corruptos).
    return items[0]


# --- LÓGICA PRINCIPAL ---

print(f"--- Consultando la tabla {TABLE_NAME} en {AWS_REGION} ---")

try:
    # 1. Conexión
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    table_log = dynamodb.Table(TABLE_NAME)

    # 2. Obtener el conteo total y el último log
    total_count = get_total_count(table_log)
    latest_log = get_latest_log(table_log)

    # 3. Preparar el objeto JSON de salida
    output_data = {
        "total_logs": total_count,
        "ultimo_registro": {}
    }

    if latest_log:
        # Mostramos todos los campos para facilitar la depuración
        output_data['ultimo_registro'] = {
            "id_log_entry": latest_log.get('id', 'N/A_ID'),
            "timestamp": latest_log.get('timestamp', 'N/A_TIME'),
            "action": latest_log.get('action', 'N/A_ACTION'),
            "client_uuid": latest_log.get('CPUid', 'N/A'),
            "session_id": latest_log.get('sessionid', 'N/A'),
            "details": latest_log.get('details', 'N/A')
        }

    # 4. Imprimir el JSON final
    print("\n--- JSON de Auditoría ---")
    print(json.dumps(output_data, indent=4, cls=DecimalEncoder))

except ClientError as e:
    print(f"\n*** ERROR: Fallo en la conexión a AWS ***")
    print(f"Mensaje: {e.response['Error']['Message']}", file=sys.stderr)
except Exception as e:
    print(f"\n*** ERROR INESPERADO: {e} ***")
