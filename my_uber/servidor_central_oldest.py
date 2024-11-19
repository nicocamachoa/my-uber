# servidor_central.py

import zmq
import threading

# Dirección IP y puerto para recibir posiciones de taxis
TAXI_POSITION_IP = "0.0.0.0"
TAXI_POSITION_PORT = 5555

# Dirección IP y puerto para enviar asignaciones a taxis
TAXI_ASSIGN_IP = "0.0.0.0"
TAXI_ASSIGN_PORT = 5556

# Lista para almacenar taxis registrados y sus posiciones
taxis_registrados = {}

def recibir_posiciones():
	context = zmq.Context()
	socket = context.socket(zmq.SUB)
	socket.bind(f"tcp://{TAXI_POSITION_IP}:{TAXI_POSITION_PORT}")
	socket.setsockopt_string(zmq.SUBSCRIBE, "")
	while True:
		mensaje = socket.recv_string()
		id_taxi, posicion = mensaje.split(":")
		taxis_registrados[id_taxi] = posicion
		print(f"Posición actualizada - Taxi {id_taxi}: {posicion}")

def asignar_servicio():
	context = zmq.Context()
	socket = context.socket(zmq.PUB)
	socket.bind(f"tcp://{TAXI_ASSIGN_IP}:{TAXI_ASSIGN_PORT}")
	while True:
		if taxis_registrados:
			id_taxi = list(taxis_registrados.keys())[0]  # Selecciona el primer taxi disponible
			mensaje = f"Asignado:{id_taxi}"
			socket.send_string(mensaje)
			print(f"Servicio asignado al Taxi {id_taxi}")
			# Remover taxi de la lista temporalmente
			del taxis_registrados[id_taxi]
		else:
			print("No hay taxis disponibles para asignar.")
		# Esperar antes de intentar asignar de nuevo
		time.sleep(10)

if __name__ == "__main__":
	import time
	# Iniciar hilo para recibir posiciones
	threading.Thread(target=recibir_posiciones).start()
	# Iniciar hilo para asignar servicios
	threading.Thread(target=asignar_servicio).start()
