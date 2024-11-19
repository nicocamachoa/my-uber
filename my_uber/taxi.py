# taxi.py

import zmq
import sys
import threading
import time
import random
import json
import os
from threading import Lock

# Configuración del archivo para registro histórico
MOVIMIENTO_ARCHIVO = "movimiento_taxi.json"
movimiento_historial = []

# Variables para rastrear métricas
tiempo_ocupado = 0  # Tiempo total ocupado (en segundos)
tiempo_libre = 0  # Tiempo total libre (en segundos)
ultimo_cambio_estado = time.time()  # Marca de tiempo del último cambio de estado

METRICAS_ARCHIVO = "metricas_taxi.json"
metricas = {"tiempo_ocupado": 0, "tiempo_libre": 0}

def guardar_metricas():
	"""Guarda las métricas de tiempo en un archivo JSON."""
	try:
		metricas["tiempo_ocupado"] = tiempo_ocupado
		metricas["tiempo_libre"] = tiempo_libre
		with open(METRICAS_ARCHIVO, "w") as archivo:
			json.dump(metricas, archivo, indent=4)
		print("Métricas actualizadas.")
	except IOError as e:
		print(f"Error al guardar métricas: {e}")

def cargar_metricas():
	"""Carga las métricas de tiempo del archivo JSON si existe."""
	global tiempo_ocupado, tiempo_libre
	if os.path.exists(METRICAS_ARCHIVO):
		try:
			with open(METRICAS_ARCHIVO, "r") as archivo:
				datos = json.load(archivo)
				tiempo_ocupado = datos.get("tiempo_ocupado", 0)
				tiempo_libre = datos.get("tiempo_libre", 0)
				print("Métricas cargadas.")
		except (IOError, json.JSONDecodeError) as e:
			print(f"Error al cargar métricas: {e}. Iniciando métricas desde cero.")


def guardar_movimiento_historial():
	"""Guarda el historial de movimiento en un archivo JSON."""
	try:
		with open(MOVIMIENTO_ARCHIVO, "w") as archivo:
			json.dump(movimiento_historial, archivo, indent=4)
		print("Historial de movimiento actualizado.")
	except IOError as e:
		print(f"Error al guardar el historial de movimiento: {e}")

def cargar_movimiento_historial():
	"""Carga el historial de movimiento del archivo JSON si existe."""
	global movimiento_historial
	if os.path.exists(MOVIMIENTO_ARCHIVO):
		try:
			with open(MOVIMIENTO_ARCHIVO, "r") as archivo:
				movimiento_historial = json.load(archivo)
				print("Historial de movimiento cargado.")
		except (IOError, json.JSONDecodeError) as e:
			print(f"Error al cargar el historial de movimiento: {e}. Iniciando desde cero.")

# Validar argumentos
if len(sys.argv) != 7:
	print("Uso: python taxi.py <ID> <N> <M> <X> <Y> <Velocidad>")
	sys.exit(1)

id_taxi = sys.argv[1]
N = int(sys.argv[2])  # Tamaño de la cuadrícula (filas)
M = int(sys.argv[3])  # Tamaño de la cuadrícula (columnas)
x = int(sys.argv[4])  # Posición inicial x
y = int(sys.argv[5])  # Posición inicial y
velocidad = int(sys.argv[6])  # Velocidad del taxi

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
posicion_inicial = (x, y)  # Guardar la posición inicial
intervalo_movimiento = max(1, 60 // velocidad)  # Intervalo de movimiento en segundos

ocupado_lock = Lock()
ocupado = False  # Indica si el taxi está ocupado con un cliente

def mover_taxi():
	"""Simula el movimiento del taxi dentro de los límites."""
	global x, y, ocupado, tiempo_libre, ultimo_cambio_estado
	while servicios_completados < servicios_diarios:
		if velocidad > 0 and not ocupado:
			# Actualizar tiempo libre
			tiempo_libre += time.time() - ultimo_cambio_estado
			ultimo_cambio_estado = time.time()
			
			# Movimiento
			direccion = random.choice([0, 1])
			desplazamiento = random.randint(1, velocidad)

			if direccion == 0:  # Movimiento horizontal
				if random.choice([True, False]):  # Derecha o izquierda
					x = min(x + desplazamiento, N)  # Mover derecha
				else:
					x = max(x - desplazamiento, 0)  # Mover izquierda
			else:  # Movimiento vertical
				if random.choice([True, False]):  # Arriba o abajo
					y = min(y + desplazamiento, M)  # Mover arriba
				else:
					y = max(y - desplazamiento, 0)  # Mover abajo

			print(f"Taxi {id_taxi} se movió a la posición ({x}, {y})")
			movimiento_historial.append({"id_taxi": id_taxi, "posicion": (x, y), "timestamp": time.time()})
			guardar_movimiento_historial()
		else:
			print(f"Taxi {id_taxi} está detenido o ocupado.")

		time.sleep(intervalo_movimiento)

def enviar_posiciones():
	"""Envía la posición del taxi al servidor central periódicamente."""
	context = zmq.Context()
	socket = context.socket(zmq.PUB)
	while True:
		try:
			socket.connect(f"tcp://{SERVER_IP}:{TAXI_POSITION_PORT}")
			while servicios_completados < servicios_diarios:
				posicion = f"({x},{y})"
				mensaje = f"{id_taxi}:{posicion}"
				socket.send_string(mensaje)
				print(f"Taxi {id_taxi} envió su posición: {posicion}")
				time.sleep(intervalo_movimiento)
			break
		except zmq.error.ZMQError as e:
			print(f"Error enviando posiciones. Reintentando... {e}")
			time.sleep(5)

	print(f"Taxi {id_taxi} ha completado todos sus servicios diarios.")
	socket.close()

def recibir_asignaciones():
	"""Recibe asignaciones de servicios del servidor central."""
	context = zmq.Context()
	socket = context.socket(zmq.SUB)
	socket.setsockopt_string(zmq.SUBSCRIBE, "")
	while True:
		try:
			socket.connect(f"tcp://{SERVER_IP}:{TAXI_ASSIGN_PORT}")
			global servicios_completados, ocupado, x, y
			while servicios_completados < servicios_diarios:
				mensaje = socket.recv_string()
				id_taxi_asignado, comando = mensaje.split(":")
				if id_taxi_asignado == id_taxi and comando == "asignado":
					print(f"Taxi {id_taxi} recibió asignación de servicio.")
					with ocupado_lock:
						global tiempo_libre, ultimo_cambio_estado
						tiempo_libre += time.time() - ultimo_cambio_estado
						ultimo_cambio_estado = time.time()
						ocupado = True

					# Simular servicio
					time.sleep(30)  # 30 minutos del sistema
					global tiempo_ocupado
					tiempo_ocupado += time.time() - ultimo_cambio_estado
					ultimo_cambio_estado = time.time()
					with ocupado_lock:
						servicios_completados += 1
					print(f"Taxi {id_taxi} finalizó el servicio {servicios_completados}. Regresando a la posición inicial {posicion_inicial}...")
					x, y = posicion_inicial
					movimiento_historial.append({"id_taxi": id_taxi, "posicion": posicion_inicial, "timestamp": time.time()})
					guardar_movimiento_historial()

					with ocupado_lock:
						ocupado = False
				else:
					print(f"Taxi {id_taxi} ignoró mensaje para Taxi {id_taxi_asignado}.")
			break
		except zmq.error.ZMQError as e:
			print(f"Error recibiendo asignaciones. Reintentando... {e}")
			time.sleep(5)

	print(f"Taxi {id_taxi} completó todos sus servicios diarios.")
	guardar_metricas()  # Guardar métricas al finalizar
	print(f"Métricas finales para Taxi {id_taxi}:")
	print(f"Tiempo total ocupado: {tiempo_ocupado:.2f} segundos")
	print(f"Tiempo total libre: {tiempo_libre:.2f} segundos")
	socket.close()

if __name__ == "__main__":
	cargar_movimiento_historial()
	cargar_metricas()
	try:
		threading.Thread(target=enviar_posiciones).start()
		threading.Thread(target=recibir_asignaciones).start()
		threading.Thread(target=mover_taxi).start()
	except KeyboardInterrupt:
		guardar_metricas()  # Guardar métricas en caso de interrupción
		print(f"Métricas finales para Taxi {id_taxi}:")
		print(f"Tiempo total ocupado: {tiempo_ocupado:.2f} segundos")
		print(f"Tiempo total libre: {tiempo_libre:.2f} segundos")
		sys.exit(0)