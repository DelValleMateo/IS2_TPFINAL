# src/observerclient.py
import socket, sys, argparse, json, uuid, time

def get_cpu_id():
    return str(uuid.getnode())

def connect_and_listen(host, port, client_uuid, verbose):
    request_json = json.dumps({"ACTION": "subscribe", "UUID": client_uuid})
    retry_delay = 30 # Segundos de espera para reconexión

    while True: # Bucle de reconexión
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                if verbose: print(f"Intentando conectar a {host}:{port}...")
                sock.connect((host, port))
                
                if verbose: print("¡Conectado! Enviando suscripción...")
                sock.sendall(request_json.encode('utf-8'))

                response = json.loads(sock.recv(1024).decode('utf-8'))
                if response.get("status") != "OK":
                    print(f"Error de suscripción: {response.get('message')}. Reintentando...")
                    time.sleep(retry_delay / 2)
                    continue

                print(f"Suscripción exitosa (UUID: {client_uuid}). Escuchando...")

                while True: # Bucle de escucha
                    notification_raw = sock.recv(4096)
                    if not notification_raw:
                        raise ConnectionError("Servidor cerró la conexión.")
                    
                    print("\n--- NOTIFICACIÓN RECIBIDA ---")
                    try:
                        parsed = json.loads(notification_raw.decode('utf-8'))
                        print(json.dumps(parsed, indent=4))
                    except json.JSONDecodeError:
                        print(notification_raw.decode('utf-8')) # Imprimir raw
                    print("-----------------------------")

        except (socket.error, ConnectionError, ConnectionResetError) as e:
            print(f"\nError de conexión: {e}", file=sys.stderr)
            print(f"Servidor caído. Reintentando en {retry_delay} segundos...")
            time.sleep(retry_delay)
        except KeyboardInterrupt:
            print("\nCerrando cliente observador...")
            break
        except Exception as e:
            print(f"Error inesperado: {e}. Reintentando...", file=sys.stderr)
            time.sleep(retry_delay / 2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente Observador TPFI")
    parser.add_argument('-s', '--server', default='localhost', help='Host del servidor')
    parser.add_argument('-p', '--port', type=int, default=8080, help='Puerto del servidor')
    parser.add_argument('-v', '--verbose', action='store_true', help='Modo verboso')
    args = parser.parse_args()
    
    connect_and_listen(args.server, args.port, get_cpu_id(), args.verbose)