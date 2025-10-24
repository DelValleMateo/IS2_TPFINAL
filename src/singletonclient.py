# src/singletonclient.py
import socket, sys, argparse, json, uuid

def get_cpu_id():
    return str(uuid.getnode())

def main():
    parser = argparse.ArgumentParser(description="Cliente 'get/set/list' TPFI")
    parser.add_argument('-i', '--input', required=True, help='Archivo JSON de entrada.')
    parser.add_argument('-o', '--output', help='(Opcional) Archivo JSON de salida.')
    parser.add_argument('-s', '--server', default='localhost', help='Host del servidor')
    parser.add_argument('-p', '--port', type=int, default=8080, help='Puerto del servidor')
    parser.add_argument('-v', '--verbose', action='store_true', help='Modo verboso')
    args = parser.parse_args()

    try:
        with open(args.input, 'r') as f:
            request_data = json.load(f)
    except Exception as e:
        print(f"Error al leer el archivo de entrada '{args.input}': {e}", file=sys.stderr)
        sys.exit(1)

    if "UUID" not in request_data:
        request_data["UUID"] = get_cpu_id()
    
    request_json = json.dumps(request_data)
    if args.verbose:
        print(f"Conectando a {args.server}:{args.port} -> Enviando: {request_json}")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((args.server, args.port))
            sock.sendall(request_json.encode('utf-8'))
            
            buffer = b""
            while True:
                data_chunk = sock.recv(1024)
                if not data_chunk:
                    break
                buffer += data_chunk
            response_data = buffer.decode('utf-8')

    except socket.error as e:
        print(f"Error: No se pudo conectar a {args.server}:{args.port}. ¿Servidor caído?", file=sys.stderr)
        sys.exit(1)

    if args.output:
        try:
            with open(args.output, 'w') as f:
                f.write(response_data) # Guardar raw
            print(f"Respuesta guardada en {args.output}")
        except IOError as e:
            print(f"Error al escribir en el archivo de salida: {e}", file=sys.stderr)
    else:
        print("\n--- Respuesta del Servidor ---")
        try:
            # Intentar imprimirlo bonito
            print(json.dumps(json.loads(response_data), indent=4))
        except json.JSONDecodeError:
            print(response_data) # Imprimir raw si no es JSON
        print("------------------------------")

if __name__ == "__main__":
    main()