# src/modules/observer.py
import threading, json, socket

class Subject:
    def __init__(self):
        self._observers = []
        self._lock = threading.Lock()
        print("Subject (Observer) inicializado.")

    def subscribe(self, client_socket, client_uuid):
        with self._lock:
            if client_socket not in self._observers:
                self._observers.append(client_socket)
                print(f"OBSERVER: Nuevo suscriptor (UUID: {client_uuid}). Total: {len(self._observers)}")

    def unsubscribe(self, client_socket):
        with self._lock:
            if client_socket in self._observers:
                try:
                    self._observers.remove(client_socket)
                    print(f"OBSERVER: Suscriptor desconectado. Total: {len(self._observers)}")
                except ValueError:
                    pass # Ya fue removido por otro hilo

    def notify(self, data, encoder_class):
        with self._lock:
            if not self._observers:
                return
            
            print(f"OBSERVER: Notificando a {len(self._observers)} suscriptor(es)...")
            message_bytes = json.dumps({"EVENT": "update", "DATA": data}, cls=encoder_class).encode('utf-8')

            for obs_socket in list(self._observers): # Iterar sobre una copia
                try:
                    obs_socket.sendall(message_bytes)
                except socket.error as e:
                    print(f"OBSERVER: Error enviando a un suscriptor ({e}). Eliminándolo.")
                    self.unsubscribe(obs_socket)