import zmq
import sys
import threading
import time
import random
import json
import os

# Archivo para estadísticas
ESTADISTICAS_ARCHIVO = "estadisticas_usuario.json"
estadisticas = {
	"solicitudes_exitosas": 0,
	"solicitudes_fallidas": 0,
	"tiempos_respuesta": []
}

def guardar_estadisticas():
	"""Guarda las estadísticas en un archivo JSON."""
	try:
		with open(ESTADISTICAS_ARCHIVO, "w") as archivo:
			json.dump(estadisticas, archivo, indent=4)
		print("Estadísticas actualizadas en estadisticas_usuario.json")
	except IOError as e:
		print(f"Error al guardar estadísticas: {e}")

def cargar_estadisticas():
	"""Carga estadísticas de un archivo JSON si existe."""
	global estadisticas
	if os.path.exists(ESTADISTICAS_ARCHIVO):
		try:
			with open(ESTADISTICAS_ARCHIVO, "r") as archivo:
				estadisticas = json.load(archivo)
				print("Estadísticas cargadas desde estadisticas_usuario.json")
		except (IOError, json.JSONDecodeError) as e:
			print(f"Error al cargar estadísticas: {e}. Iniciando desde cero.")

def hilo_usuario(id_usuario, posicion, tiempo_espera):
	"""Función que representa el comportamiento de un usuario."""
	x, y = posicion
	print(f"Usuario {id_usuario} inicializado en posición ({x}, {y}). Esperará {tiempo_espera} minutos para pedir un taxi.")

	# Dormir hasta que el usuario necesite un taxi
	time.sleep(tiempo_espera)

	print(f"Usuario {id_usuario} solicita un taxi desde posición ({x}, {y}).")

	# Crear contexto y socket ZeroMQ para request-reply
	context = zmq.Context()
	socket = context.socket(zmq.REQ)
	socket.connect(f"tcp://{SERVER_IP}:{SERVER_PORT}")
	socket.RCVTIMEO = 5000  # Tiempo de espera máximo en milisegundos (5 segundos)

	# Enviar solicitud al servidor
	mensaje_solicitud = json.dumps({"id_usuario": id_usuario, "x": x, "y": y})
	tiempo_inicio = time.time()

	try:
		socket.send_string(mensaje_solicitud)
		respuesta = json.loads(socket.recv_string())
		tiempo_respuesta = time.time() - tiempo_inicio

		if respuesta["status"] == "asignado":
			print(f"Usuario {id_usuario} recibió un taxi {respuesta['taxi_id']}. Tiempo de respuesta: {tiempo_respuesta:.2f} segundos.")
			with lock:
				estadisticas["solicitudes_exitosas"] += 1
		else:
			print(f"Usuario {id_usuario} no recibió un taxi. Respuesta: {respuesta['mensaje']}.")
			with lock:
				estadisticas["solicitudes_fallidas"] += 1

		estadisticas["tiempos_respuesta"].append(tiempo_respuesta)

	except zmq.error.Again:
		print(f"Usuario {id_usuario} no recibió respuesta del servidor (timeout).")
		with lock:
			estadisticas["solicitudes_fallidas"] += 1
	finally:
		guardar_estadisticas()
		socket.close()
		context.term()

def generador_usuarios(Y, archivo_coordenadas):
	"""Crea Y hilos representando a los usuarios."""
	hilos = []
	try:
		with open(archivo_coordenadas, "r") as f:
			for i in range(Y):
				linea = f.readline().strip()
				if not linea:  # Si la línea está vacía
					break
				x, y = map(int, linea.split(","))
				tiempo_espera = random.randint(1, 5)  # Tiempo aleatorio en minutos (simulados como segundos)
				hilo = threading.Thread(target=hilo_usuario, args=(i + 1, (x, y), tiempo_espera))
				hilos.append(hilo)
				hilo.start()
	except FileNotFoundError:
		print(f"Error: El archivo '{archivo_coordenadas}' no existe.")
		sys.exit(1)
	except ValueError:
		print("Error: El archivo debe contener coordenadas en formato X,Y.")
		sys.exit(1)

	# Esperar a que todos los hilos terminen
	for hilo in hilos:
		hilo.join()

	# Mostrar estadísticas finales
	print("Resultados finales:")
	print(f"Solicitudes exitosas: {estadisticas['solicitudes_exitosas']}")
	print(f"Solicitudes fallidas: {estadisticas['solicitudes_fallidas']}")

# Parámetros iniciales
if len(sys.argv) != 5:
	print("Uso: python usuario.py <N> <M> <Y> <archivo_coordenadas>")
	sys.exit(1)

N = int(sys.argv[1])  # Tamaño de la cuadrícula (filas)
M = int(sys.argv[2])  # Tamaño de la cuadrícula (columnas)
Y = int(sys.argv[3])  # Número de usuarios a generar
archivo_coordenadas = sys.argv[4]  # Archivo con coordenadas

# Dirección del servidor
SERVER_IP = "127.0.0.1"
SERVER_PORT = 5557  # Puerto para solicitudes de taxis

# Variables para resultados
lock = threading.Lock()

# Iniciar el generador de usuarios
if __name__ == "__main__":
	cargar_estadisticas()
	generador_usuarios(Y, archivo_coordenadas)
