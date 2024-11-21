# taxi.py

import zmq
import sys
import threading
import time

# Validar argumentos
if len(sys.argv) != 7:
    print("Uso: python taxi.py <ID> <N> <M> <X> <Y> <Velocidad>")
    sys.exit(1)

id_taxi = sys.argv[1]
N = int(sys.argv[2])
M = int(sys.argv[3])
x = int(sys.argv[4])
y = int(sys.argv[5])
velocidad = int(sys.argv[6])

# Validar posición inicial
if not (0 <= x <= N and 0 <= y <= M):
    print("Posición inicial fuera de los límites de la cuadrícula.")
    sys.exit(1)

# Dirección IP y puerto del servidor central
SERVER_IP = "127.0.0.1"
TAXI_POSITION_PORT = 5555
TAXI_ASSIGN_PORT = 5556

def enviar_posiciones():
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.connect(f"tcp://{SERVER_IP}:{TAXI_POSITION_PORT}")
    while True:
        posicion = f"({x},{y})"
        mensaje = f"{id_taxi}:{posicion}"
        socket.send_string(mensaje)
        print(f"Taxi {id_taxi} envió su posición: {posicion}")
        time.sleep(5)  # Enviar posición cada 5 segundos

def recibir_asignaciones():
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(f"tcp://{SERVER_IP}:{TAXI_ASSIGN_PORT}")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    while True:
        mensaje = socket.recv_string()
        comando, id_taxi_asignado = mensaje.split(":")
        if id_taxi_asignado == id_taxi:
            print(f"Taxi {id_taxi} recibió asignación de servicio.")
            # Simular que está ocupado
            time.sleep(10)
            print(f"Taxi {id_taxi} finalizó el servicio.")
            # Volver a enviar posiciones
        else:
            print(f"Taxi {id_taxi} ignoró mensaje para Taxi {id_taxi_asignado}")

if __name__ == "__main__":
    # Iniciar hilo para enviar posiciones
    threading.Thread(target=enviar_posiciones).start()
    # Iniciar hilo para recibir asignaciones
    threading.Thread(target=recibir_asignaciones).start()
