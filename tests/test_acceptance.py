# tests/test_acceptance.py
import unittest
import subprocess
import os
import sys
import time
import json
import boto3
from botocore.exceptions import ClientError

# --- Configuración (Lo más corto posible) ---
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SERVER = os.path.join(ROOT, 'src', 'singletonproxyobserver.py')
CLIENT = os.path.join(ROOT, 'src', 'singletonclient.py')
PORT = 8081
JSON_GET = os.path.join(ROOT, 'data', 'test_get.json')
JSON_SET = os.path.join(ROOT, 'data', 'test_set.json')
JSON_LIST = os.path.join(ROOT, 'data', 'test_list.json')


class TestAcceptance(unittest.TestCase):
    server_process, log_table = None, None

    @classmethod
    def setUpClass(cls):
        print("Configurando pruebas...")
        try:
            cls.log_table = boto3.resource('dynamodb').Table('CorporateLog')
            cls.log_table.load()
        except Exception as e:
            print(f"ERROR: No se pudo conectar a AWS. {e}")
            sys.exit(1)

    def setUp(self): self.stop_server(); time.sleep(0.5)
    def tearDown(self): self.stop_server()

    def start_server(self, port=PORT):
        print(f"\nIniciando servidor en puerto {port}...")
        # --- CAMBIO AQUÍ ---
        # Quitamos 'stdout' y 'stderr' para que el servidor imprima
        # directamente en esta terminal.
        self.server_process = subprocess.Popen(
            [sys.executable, SERVER, '-p', str(port)],
            text=True
        )
        time.sleep(1.5)
        print("Servidor iniciado.")

    def stop_server(self):
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait()
            # --- CAMBIO AQUÍ ---
            # Ya no cerramos los pipes porque no existen.
            self.server_process = None
            print("Servidor detenido.")

    def run_client(self, args):
        # El cliente sí captura la salida para que podamos imprimirla
        return subprocess.run([sys.executable, CLIENT] + args, capture_output=True, text=True, cwd=ROOT)

    def get_log_count(self):
        try:
            return self.log_table.scan(Select='COUNT')['Count']
        except:
            return -1

    # --- Casos de Prueba (Versión Ruidosa) ---

    def test_01_camino_feliz_y_auditoria(self):
        print("\n--- Test 01: Camino Feliz (set, get, list) y Auditoría ---")
        self.start_server()
        logs_ini = self.get_log_count()

        print("Probando SET...")
        res_set = self.run_client(['-i', JSON_SET, '-p', str(PORT)])
        print("--- Salida del Cliente (SET) ---")
        print(res_set.stdout)
        print("--- Errores del Cliente (SET) ---")
        print(res_set.stderr)
        self.assertEqual(res_set.returncode, 0)
        logs_set = self.get_log_count()
        self.assertEqual(logs_set, logs_ini + 1, "SET no generó log.")

        print("Probando GET...")
        res_get = self.run_client(['-i', JSON_GET, '-p', str(PORT)])
        print("--- Salida del Cliente (GET) ---")
        print(res_get.stdout)
        print("--- Errores del Cliente (GET) ---")
        print(res_get.stderr)
        self.assertEqual(res_get.returncode, 0)
        logs_get = self.get_log_count()
        self.assertEqual(logs_get, logs_set + 1, "GET no generó log.")

        print("Probando LIST...")
        res_list = self.run_client(['-i', JSON_LIST, '-p', str(PORT)])
        print("--- Salida del Cliente (LIST) ---")
        print(res_list.stdout)
        print("--- Errores del Cliente (LIST) ---")
        print(res_list.stderr)
        self.assertEqual(res_list.returncode, 0)
        logs_list = self.get_log_count()
        self.assertEqual(logs_list, logs_get + 1, "LIST no generó log.")
        print("--- Test 01 Superado ---")

    def test_02_argumentos_malformados(self):
        print("\n--- Test 02: Argumentos Malformados (Cliente) ---")
        res = self.run_client(['-p', str(PORT)])  # Falta -i
        print("--- Salida del Cliente (Malformado) ---")
        print(res.stdout)
        print("--- Errores del Cliente (Malformado) ---")
        print(res.stderr)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("required: -i/--input", res.stderr)
        print("--- Test 02 Superado ---")

    def test_03_requerimiento_datos_minimos(self):
        print("\n--- Test 03: Requerimiento sin Datos Mínimos (GET sin ID) ---")
        self.start_server()
        temp_json = os.path.join(ROOT, 'data', 'temp.json')
        with open(temp_json, 'w') as f:
            json.dump({"ACTION": "get"}, f)

        res = self.run_client(['-i', temp_json, '-p', str(PORT)])
        print("--- Salida del Cliente (GET sin ID) ---")
        print(res.stdout)
        print("--- Errores del Cliente (GET sin ID) ---")
        print(res.stderr)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Missing ID", res.stdout)
        os.remove(temp_json)
        print("--- Test 03 Superado ---")

    def test_04_manejo_server_caido(self):
        print("\n--- Test 04: Cliente con Servidor Caído ---")
        res = self.run_client(['-i', JSON_GET, '-p', str(PORT)])
        print("--- Salida del Cliente (Servidor Caído) ---")
        print(res.stdout)
        print("--- Errores del Cliente (Servidor Caído) ---")
        print(res.stderr)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("No se pudo conectar", res.stderr)
        print("--- Test 04 Superado ---")

    def test_05_intento_levantar_dos_servidores(self):
        print("\n--- Test 05: Doble Servidor en mismo Puerto ---")
        self.start_server()  # Inicia el Servidor 1

        print("Intentando iniciar segundo servidor...")
        result_server2 = subprocess.run(
            [sys.executable, SERVER, '-p', str(PORT)],
            capture_output=True, text=True
        )

        print("--- Salida del Servidor 2 (STDOUT) ---")
        print(result_server2.stdout)
        print("--- Salida del Servidor 2 (STDERR) ---")
        print(result_server2.stderr)

        self.assertNotEqual(result_server2.returncode, 0,
                            "El segundo servidor no falló como se esperaba.")

        self.assertIn("Error de Socket", result_server2.stderr)
        print("Error de Socket capturado correctamente.")
        print("--- Test 05 Superado ---")


if __name__ == '__main__':
    unittest.main()
