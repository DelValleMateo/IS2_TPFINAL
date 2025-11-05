# src/singletonproxyobserver.py
import socket
import sys
import argparse
import json
import uuid
import threading
from decimal import Decimal
from modules.db_singleton import DatabaseSingleton
from modules.data_proxy import DataProxy
from modules.observer import Subject

VERSION = "1.0-conciso"


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        return str(obj) if isinstance(obj, Decimal) else super(DecimalEncoder, self).default(obj)


class Server:
    def __init__(self, host, port):
        self.host, self.port = host, port
        print("Inicializando componentes del servidor...")
        self.data_proxy = DataProxy()
        self.subject = Subject()
        print("--- Servidor listo para escuchar ---")

    def _send_response(self, conn, data, status_code=200):
        """Helper para enviar respuestas JSON."""
        print(f"Enviando respuesta (Status: {status_code})")
        conn.sendall(json.dumps(data, cls=DecimalEncoder,
                     indent=4).encode('utf-8'))

    def handle_client_connection(self, conn, addr):
        print(
            f"Manejando conexión de {addr} en hilo {threading.current_thread().name}")
        is_subscriber = False
        data = {}
        try:
            request_raw = conn.recv(4096)
            if not request_raw:
                return print(f"Cliente {addr} desconectado sin datos.")

            print(f"Datos recibidos de {addr}: {request_raw.decode('utf-8')}")
            data = json.loads(request_raw.decode('utf-8'))
            action = data.get("ACTION")
            client_uuid = data.get("UUID", "UUID_DESCONOCIDO")
            session_id = str(uuid.uuid4())

            # --- LÓGICA DE ACCIONES Y NOTIFICACIÓN ---
            if action == "get":
                item_id = data.get("id") or data.get("ID")
                if item_id:
                    resp_data, status = self.data_proxy.get_item(
                        item_id, client_uuid, session_id
                    )
                    # IMPORTANTE: GET NO NOTIFICA
                else:
                    resp_data, status = {"error": "Missing ID"}, 400

            elif action == "set":
                if "id" in data or "ID" in data:
                    resp_data, status = self.data_proxy.set_item(
                        data, client_uuid, session_id
                    )
                    # SOLO ACÁ notificamos porque es una actualización de datos
                    if status == 200:
                        self.subject.notify(
                            {"action": action, "data": resp_data}, DecimalEncoder
                        )
                else:
                    resp_data, status = {"error": "Missing ID"}, 400

            elif action == "list":
                resp_data, status = self.data_proxy.list_items(
                    client_uuid, session_id
                )
                # IMPORTANTE: LIST NO NOTIFICA

            elif action == "listlog":
                resp_data, status = self.data_proxy.list_logs(
                    client_uuid, session_id
                )

            elif action == "subscribe":
                self.data_proxy._log_action(
                    client_uuid, session_id, "subscribe")
                self.subject.subscribe(conn, client_uuid)
                is_subscriber = True
                resp_data, status = {"status": "OK",
                                     "message": "Suscrito"}, 200

            else:
                resp_data, status = {"error": "Unknown Action"}, 400

            # Respuesta centralizada
            self._send_response(conn, resp_data, status)

            if is_subscriber:
                print(
                    f"Cliente {addr} (UUID: {client_uuid}) suscrito. Hilo en espera.")
                while conn.recv(1024):  # Esperar desconexión
                    pass

        except json.JSONDecodeError:
            self._send_response(conn, {"error": "Invalid JSON"}, 400)
        except (socket.error, ConnectionResetError) as e:
            print(f"Error de Socket con {addr}: {e}")
        except Exception as e:
            print(f"Error inesperado con {addr}: {e}", file=sys.stderr)
        finally:
            if is_subscriber:
                self.subject.unsubscribe(conn)
            print(f"Cerrando conexión y finalizando hilo para {addr}.")
            conn.close()

    def start(self):
        try:
            self.server_socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            # self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Comentado para test_05
            self.server_socket.bind((self.host, self.port))

            # --- CORRECCIÓN: Solución a Control+C ---
            # Establece un timeout de 1 segundo
            self.server_socket.settimeout(1.0)

            self.server_socket.listen(5)
            print(f"Servidor {VERSION} escuchando en {self.host}:{self.port}")

            while True:
                # El accept() ahora está envuelto en un try/except para el timeout
                try:
                    conn, addr = self.server_socket.accept()
                    # Si tiene éxito, crea el hilo
                    threading.Thread(target=self.handle_client_connection, args=(
                        conn, addr), daemon=True).start()

                except socket.timeout:
                    # Si pasa el timeout, ignoramos (pass) y el bucle vuelve a empezar
                    pass
                except KeyboardInterrupt:
                    # Si ocurre Control+C, salta al except externo.
                    raise

        except socket.error as e:
            print(f"Error de Socket: {e}", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nCerrando el servidor...")
        finally:
            if hasattr(self, 'server_socket') and self.server_socket:
                self.server_socket.close()
            print("Servidor detenido.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor TPFI")
    parser.add_argument('-p', '--port', type=int,
                        default=8080, help='Puerto (default: 8080)')
    args = parser.parse_args()
    Server('0.0.0.0', args.port).start()
