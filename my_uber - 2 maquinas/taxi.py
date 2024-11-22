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
tiempo_libre = 0    # Tiempo total libre (en segundos)
ultimo_cambio_estado = time.time()  # Marca de tiempo del último cambio de estado

METRICAS_ARCHIVO = "metricas_taxi.json"
metricas = {"tiempo_ocupado": 0, "tiempo_libre": 0}
HEALTH_CHECK_PORT = 5562  # Puerto para health-check

def guardar_metricas():
	"""Guarda las métricas de tiempo en un archivo JSON."""
	global tiempo_ocupado, tiempo_libre
	try:
		metricas["tiempo_ocupado"] = tiempo_ocupado
		metricas["tiempo_libre"] = tiempo_libre
		with open(METRICAS_ARCHIVO, "w") as archivo:
			json.dump(metricas, archivo, indent=4)
		print("Métricas actualizadas.", flush=True)
	except IOError as e:
		print(f"Error al guardar métricas: {e}", flush=True)

def cargar_metricas():
	"""Carga las métricas de tiempo del archivo JSON si existe."""
	global tiempo_ocupado, tiempo_libre
	if os.path.exists(METRICAS_ARCHIVO):
		try:
			with open(METRICAS_ARCHIVO, "r") as archivo:
				datos = json.load(archivo)
				tiempo_ocupado = datos.get("tiempo_ocupado", 0)
				tiempo_libre = datos.get("tiempo_libre", 0)
				print("Métricas cargadas.", flush=True)
		except (IOError, json.JSONDecodeError) as e:
			print(f"Error al cargar métricas: {e}. Iniciando métricas desde cero.", flush=True)

def guardar_movimiento_historial():
	"""Guarda el historial de movimiento en un archivo JSON."""
	try:
		with open(MOVIMIENTO_ARCHIVO, "w") as archivo:
			json.dump(movimiento_historial, archivo, indent=4)
		print("Historial de movimiento actualizado.", flush=True)
	except IOError as e:
		print(f"Error al guardar el historial de movimiento: {e}", flush=True)

def cargar_movimiento_historial():
	"""Carga el historial de movimiento del archivo JSON si existe."""
	global movimiento_historial
	if os.path.exists(MOVIMIENTO_ARCHIVO):
		try:
			with open(MOVIMIENTO_ARCHIVO, "r") as archivo:
				movimiento_historial = json.load(archivo)
				print("Historial de movimiento cargado.", flush=True)
		except (IOError, json.JSONDecodeError) as e:
			print(f"Error al cargar el historial de movimiento: {e}. Iniciando desde cero.", flush=True)

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
	print("Posición inicial fuera de los límites de la cuadrícula.", flush=True)
	sys.exit(1)

# Dirección IP y puerto del servidor central
# Dirección IP de los servidores
SERVERS = ["10.43.100.133", "10.43.101.2"]
TAXI_POSITION_PORT = 5555
TAXI_ASSIGN_PORT = 5556

# Parámetros de servicio
servicios_diarios = 3
servicios_completados = 0
posicion_inicial = (x, y)  # Guardar la posición inicial
intervalo_movimiento = 30  # 30 segundos para simular 30 minutos

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
			direccion = random.choice([0, 1])  # 0: horizontal, 1: vertical
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

			print(f"Taxi {id_taxi} se movió a la posición ({x}, {y})", flush=True)
			movimiento_historial.append({"id_taxi": id_taxi, "posicion": (x, y), "timestamp": time.time()})
			guardar_movimiento_historial()
		else:
			print(f"Taxi {id_taxi} está detenido o ocupado.", flush=True)

		time.sleep(intervalo_movimiento)
		
def detectar_servidor_principal():
	"""Determina cuál servidor está activo realizando un health-check."""
	for server_ip in SERVERS:
		print(f"Detectando servidor activo en {server_ip}...", flush=True)
		try:
			context = zmq.Context()
			socket = context.socket(zmq.REQ)
			socket.setsockopt(zmq.RCVTIMEO, 2000)  # Timeout de 2 segundos
			socket.connect(f"tcp://{server_ip}:{HEALTH_CHECK_PORT}")
			socket.send_string("ping")
			respuesta = socket.recv_string()
			if respuesta.strip().lower() == "pong":
				print(f"Servidor activo detectado: {server_ip}", flush=True)
				socket.close()
				return server_ip
			socket.close()
		except zmq.error.Again:
			print(f"Servidor {server_ip} no respondió al health-check.", flush=True)
		except Exception as e:
			print(f"Error al verificar servidor {server_ip}: {e}", flush=True)
	print("No se pudo detectar un servidor activo.", flush=True)
	return None

def enviar_posiciones():
	context = zmq.Context()
	"""Envía la posición del taxi al servidor central periódicamente."""
	while servicios_completados < servicios_diarios:
		servidor_activo = detectar_servidor_principal()
		if not servidor_activo:
			print("No hay servidores disponibles. Reintentando en 5 segundos...", flush=True)
			time.sleep(5)
			continue

		try:
			# Cerrar conexión previa si existe
			if socket:
				socket.close()
			context = zmq.Context()
			socket = context.socket(zmq.PUSH)
			socket.connect(f"tcp://{servidor_activo}:{TAXI_POSITION_PORT}")
			posicion = f"({x},{y})"
			mensaje = f"{id_taxi}:{posicion}"
			socket.send_string(mensaje)
			print(f"Taxi {id_taxi} envió su posición: {posicion} a {servidor_activo}", flush=True)
			socket.disconnect(f"tcp://{servidor_activo}:{TAXI_POSITION_PORT}")
		except zmq.error.ZMQError as e:
			print(f"Error al enviar posición al servidor {servidor_activo}: {e}", flush=True)
		except Exception as e:
			print(f"Error inesperado al enviar posición: {e}", flush=True)
		time.sleep(intervalo_movimiento)

def enviar_posiciones():
	"""Envía la posición del taxi al servidor central periódicamente."""
	context = zmq.Context()
	intentos = 0
	max_reintentos = 5
	intervalos_espera = 5  # Espera de 5 segundos entre intentos

	while servicios_completados < servicios_diarios:
		# Detectar cuál servidor está activo
		servidor_activo = detectar_servidor_principal()
		if not servidor_activo:
			print(f"Taxi {id_taxi}: No hay servidores disponibles. Reintentando en {intervalos_espera} segundos...", flush=True)
			time.sleep(intervalos_espera)
			intentos += 1
			if intentos > max_reintentos:
				print("Error persistente al detectar servidor activo. Terminando la ejecución.", flush=True)
				break
			continue

		try:
			# Conectarse al servidor activo y enviar la posición
			socket = context.socket(zmq.PUSH)
			socket.connect(f"tcp://{servidor_activo}:{TAXI_POSITION_PORT}")
			print(f"Taxi {id_taxi} enviando posiciones a tcp://{servidor_activo}:{TAXI_POSITION_PORT}", flush=True)
			posicion = f"({x},{y})"
			mensaje = f"{id_taxi}:{posicion}"
			socket.send_string(mensaje)
			print(f"Taxi {id_taxi} envió su posición: {posicion} a {servidor_activo}", flush=True)
			socket.disconnect(f"tcp://{servidor_activo}:{TAXI_POSITION_PORT}")
			intentos = 0  # Resetear el contador de intentos tras un envío exitoso
		except zmq.error.ZMQError as e:
			print(f"Error al enviar posición al servidor {servidor_activo}: {e}", flush=True)
		except Exception as e:
			print(f"Error inesperado al enviar posición: {e}", flush=True)
		finally:
			socket.close()

		# Esperar antes de enviar la próxima posición
		time.sleep(intervalo_movimiento)

	print(f"Taxi {id_taxi} ha completado todos sus servicios diarios.", flush=True)



def recibir_asignaciones():
	"""Recibe asignaciones de servicios del servidor central."""
	context = zmq.Context()
	socket = context.socket(zmq.SUB)
	socket.setsockopt_string(zmq.SUBSCRIBE, "")
	global servicios_completados
	
	while servicios_completados < servicios_diarios:
		conectado = False
		for server_ip in SERVERS:
			try:
				socket.connect(f"tcp://{server_ip}:{TAXI_ASSIGN_PORT}")
				print(f"Taxi {id_taxi} suscrito a asignaciones en tcp://{server_ip}:{TAXI_ASSIGN_PORT}", flush=True)
				conectado = True
				break  # Salir del loop si se conecta exitosamente
			except zmq.error.ZMQError as e:
				print(f"Error conectando a {server_ip}:{TAXI_ASSIGN_PORT} para recibir asignaciones: {e}", flush=True)
				socket.disconnect(f"tcp://{server_ip}:{TAXI_ASSIGN_PORT}")
				continue  # Intentar con el siguiente servidor
			except Exception as e:
				print(f"Error en recibir_asignaciones: {e}", flush=True)
				socket.disconnect(f"tcp://{server_ip}:{TAXI_ASSIGN_PORT}")
				continue  # Intentar con el siguiente servidor
		
		if conectado:
			try:
				mensaje = socket.recv_string()
				print(f"Taxi {id_taxi} recibió mensaje: {mensaje}", flush=True)
				id_taxi_asignado, comando = mensaje.split(":")
				if id_taxi_asignado == id_taxi and comando.strip().lower() == "asignado":
					print(f"Taxi {id_taxi} recibió asignación de servicio.", flush=True)
					with ocupado_lock:
						tiempo_libre += time.time() - ultimo_cambio_estado
						ultimo_cambio_estado = time.time()
						ocupado = True

					# Simular servicio
					print(f"Taxi {id_taxi} iniciando servicio...", flush=True)
					time.sleep(30)  # Simular servicio (30 segundos para pruebas)
					tiempo_ocupado += time.time() - ultimo_cambio_estado
					ultimo_cambio_estado = time.time()
					with ocupado_lock:
						servicios_completados += 1
					print(f"Taxi {id_taxi} finalizó el servicio {servicios_completados}. Regresando a la posición inicial {posicion_inicial}...", flush=True)
					x, y = posicion_inicial
					movimiento_historial.append({"id_taxi": id_taxi, "posicion": posicion_inicial, "timestamp": time.time()})
					guardar_movimiento_historial()

					with ocupado_lock:
						ocupado = False
				else:
					print(f"Taxi {id_taxi} ignoró mensaje para Taxi {id_taxi_asignado}.", flush=True)
			except zmq.error.Again:
				print(f"Taxi {id_taxi}: Timeout esperando asignaciones.", flush=True)
			except Exception as e:
				print(f"Error en recibir_asignaciones: {e}", flush=True)
		else:
			intentos += 1
			if intentos > max_reintentos:
				print("Error persistente al recibir asignaciones. Terminando la ejecución.", flush=True)
				break
			print(f"Taxi {id_taxi}: No pudo conectar a ningún servidor para asignaciones. Reintentando en {intervalos_espera} segundos.", flush=True)
			time.sleep(intervalos_espera)

	print(f"Taxi {id_taxi} completó todos sus servicios diarios.", flush=True)
	guardar_metricas()  # Guardar métricas al finalizar
	print(f"Métricas finales para Taxi {id_taxi}:", flush=True)
	print(f"Tiempo total ocupado: {tiempo_ocupado:.2f} segundos", flush=True)
	print(f"Tiempo total libre: {tiempo_libre:.2f} segundos", flush=True)
	socket.close()


if __name__ == "__main__":
	cargar_movimiento_historial()
	cargar_metricas()
	try:
		# Iniciar hilos sin ser daemon
		enviar_thread = threading.Thread(target=enviar_posiciones)
		recibir_thread = threading.Thread(target=recibir_asignaciones)
		mover_thread = threading.Thread(target=mover_taxi)
		
		enviar_thread.start()
		recibir_thread.start()
		mover_thread.start()
		
		# Mantener el hilo principal activo hasta que los hilos de trabajo terminen
		enviar_thread.join()
		recibir_thread.join()
		mover_thread.join()
	except KeyboardInterrupt:
		guardar_metricas()  # Guardar métricas en caso de interrupción
		print(f"Métricas finales para Taxi {id_taxi}:", flush=True)
		print(f"Tiempo total ocupado: {tiempo_ocupado:.2f} segundos", flush=True)
		print(f"Tiempo total libre: {tiempo_libre:.2f} segundos", flush=True)
		sys.exit(0)