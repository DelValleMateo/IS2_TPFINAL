import subprocess
import os
import sys
import time
import boto3
import json

# --- 1. Configuración (¡Ajusta esto!) ---
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SERVER = os.path.join(ROOT, 'src', 'singletonproxyobserver.py')
CLIENT = os.path.join(ROOT, 'src', 'singletonclient.py')
PORT = 8081

# Archivos JSON para las pruebas
JSON_SET = os.path.join(ROOT, 'data', 'test_set.json')
JSON_GET = os.path.join(ROOT, 'data', 'test_get.json')
JSON_LIST = os.path.join(ROOT, 'data', 'test_list.json')

# IMPORTANTE: Especifica tu región de AWS aquí
AWS_REGION = "us-east-1"  # Asumo us-east-1 de nuestros logs anteriores

# --- 2. Variable global para el servidor ---
server_process = None
log_table = None

# --- 3. Funciones de Ayuda ---


def start_server():
    """Inicia el servidor en un subproceso (mostrando su salida)."""
    global server_process
    print(f"\nIniciando servidor en puerto {PORT}...")
    server_process = subprocess.Popen(
        [sys.executable, SERVER, '-p', str(PORT)],
        text=True
    )
    time.sleep(2)  # Dar tiempo al servidor para inicializar
    print("Servidor iniciado.")


def stop_server():
    """Detiene el servidor si está corriendo."""
    global server_process
    if server_process:
        server_process.terminate()
        server_process.wait()
        print("Servidor detenido.")


def run_client(action_name, json_file_path):
    """Ejecuta el cliente y reporta si tuvo éxito."""
    print(f"--- Probando: {action_name} ---")
    args = ['-i', json_file_path, '-p', str(PORT)]

    result = subprocess.run(
        [sys.executable, CLIENT] + args,
        capture_output=True, text=True, cwd=ROOT
    )

    if result.returncode != 0:
        print(f"¡ERROR! El cliente de {action_name} falló.")
        print(result.stderr)
        return False

    print(f"Respuesta del servidor (stdout del cliente):")
    print(result.stdout)
    return True


def get_log_count():
    """Obtiene el conteo de logs actual."""
    global log_table
    try:
        count = log_table.scan(Select='COUNT', ConsistentRead=True)['Count']
        return count
    except Exception as e:
        print(f"Error al contar logs: {e}")
        return -1


def wait_for_log_count(expected_count, timeout_secs=30):
    """
    Espera hasta que el conteo de logs sea el esperado.
    Esta es la función clave para tests consistentes.
    """
    print(f"Esperando que el conteo de logs llegue a {expected_count}...")
    start_time = time.time()
    while time.time() - start_time < timeout_secs:
        current_count = get_log_count()
        if current_count == expected_count:
            print(f"¡Conteo verificado! ({current_count})")
            return True
        print(f"Conteo actual: {current_count}. Esperando...")
        time.sleep(1)

    print(
        f"¡FALLO DE TIMEOUT! Se esperaba {expected_count} pero se obtuvo {current_count}.")
    return False

# --- 4. Lógica Principal del Test ---


def run_test():
    global server_process, log_table

    try:
        # --- Conectar a AWS ---
        print("Conectando a DynamoDB...")
        dynamo = boto3.resource('dynamodb', region_name=AWS_REGION)
        log_table = dynamo.Table('CorporateLog')
        log_table.load()
        print(f"Conectado a DynamoDB (Región: {AWS_REGION}).")

        # --- Iniciar Servidor ---
        start_server()

        # --- Obtener logs iniciales ---
        logs_iniciales = get_log_count()
        if logs_iniciales == -1:
            raise Exception("No se pudo leer el conteo inicial de logs.")
        print(f"Conteo de logs inicial: {logs_iniciales}")

        # --- PASO 1: Probar SET ---
        if not run_client("SET", JSON_SET):
            raise Exception("La prueba SET falló.")

        if not wait_for_log_count(logs_iniciales + 1):
            raise Exception("¡FALLO! El log de SET no se registró a tiempo.")

        logs_despues_set = logs_iniciales + 1

        # --- PASO 2: Probar GET ---
        if not run_client("GET", JSON_GET):
            raise Exception("La prueba GET falló.")

        if not wait_for_log_count(logs_despues_set + 1):
            raise Exception("¡FALLO! El log de GET no se registró a tiempo.")

        logs_despues_get = logs_despues_set + 1

        # --- PASO 3: Probar LIST ---
        if not run_client("LIST", JSON_LIST):
            raise Exception("La prueba LIST falló.")

        if not wait_for_log_count(logs_despues_get + 1):
            raise Exception("¡FALLO! El log de LIST no se registró a tiempo.")

        print("\n--- ¡ÉXITO! Todas las pruebas del camino feliz pasaron. ---")

    except Exception as e:
        print(f"\n--- ¡TEST FALLÓ! ---")
        print(f"Error: {e}")

    finally:
        # Esto se ejecuta SIEMPRE, incluso si hay un error
        print("\n--- Limpieza ---")
        stop_server()


# --- 5. Ejecutar el Test ---
if __name__ == "__main__":
    run_test()
