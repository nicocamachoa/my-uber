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

# Parámetros de servicio
servicios_diarios = 3
servicios_completados = 0

# Intervalo de movimiento en segundos (30 minutos en el sistema)
intervalo_movimiento = 60 // velocidad  # Moverse cada 30 minutos en función de la velocidad

def enviar_posiciones():
	context = zmq.Context()
	socket = context.socket(zmq.PUB)
	socket.connect(f"tcp://{SERVER_IP}:{TAXI_POSITION_PORT}")
	
	while servicios_completados < servicios_diarios:
		posicion = f"({x},{y})"
		mensaje = f"{id_taxi}:{posicion}"
		socket.send_string(mensaje)
		print(f"Taxi {id_taxi} envió su posición: {posicion}")
		time.sleep(intervalo_movimiento)  # Ajustar intervalo según velocidad
	
	print(f"Taxi {id_taxi} ha completado todos sus servicios diarios.")

def recibir_asignaciones():
	context = zmq.Context()
	socket = context.socket(zmq.SUB)
	socket.connect(f"tcp://{SERVER_IP}:{TAXI_ASSIGN_PORT}")
	socket.setsockopt_string(zmq.SUBSCRIBE, "")
	
	global servicios_completados
	
	while servicios_completados < servicios_diarios:
		mensaje = socket.recv_string()
		comando, id_taxi_asignado = mensaje.split(":")
		
		if id_taxi_asignado == id_taxi:
			print(f"Taxi {id_taxi} recibió asignación de servicio.")
			# Simular que está ocupado por 30 minutos (30 segundos del sistema)
			time.sleep(30)
			servicios_completados += 1
			print(f"Taxi {id_taxi} finalizó el servicio. Servicios completados: {servicios_completados}")
		else:
			print(f"Taxi {id_taxi} ignoró mensaje para Taxi {id_taxi_asignado}")
	
	print(f"Taxi {id_taxi} completó todos sus servicios por hoy.")

if __name__ == "__main__":
	# Iniciar hilo para enviar posiciones
	threading.Thread(target=enviar_posiciones).start()
	# Iniciar hilo para recibir asignaciones
	threading.Thread(target=recibir_asignaciones).start()
