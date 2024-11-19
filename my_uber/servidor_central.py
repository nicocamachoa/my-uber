import zmq
import threading
import time
import json
import math
import json
import os

# Configuración de ZeroMQ
DISCOVERY_PORT = 5560  # Puerto para negociación inicial
ESTADO_SYNC_PORT = 5561  # Puerto para sincronización de estado
HEALTH_CHECK_PORT = 5562  # Puerto para health-check
TAXI_POSITION_PORT = 5555  # Puerto para recibir posiciones de taxis
USER_REQUEST_PORT = 5557  # Puerto para solicitudes de usuarios
TAXI_ASSIGN_PORT = 5556  # Puerto para asignaciones de taxis

# Estado global
taxis_registrados = {}  # ID -> (x, y)
solicitudes_usuarios = []  # Solicitudes pendientes
ROL = None  # Rol del servidor (principal o respaldo)
lock = threading.Lock()  # Lock para acceso concurrente al estado

# Archivo para guardar el estado
ESTADO_ARCHIVO = "estado_servidor.json"

def guardar_estado():
	try:
		estado = {
			"taxis_registrados": taxis_registrados,
			"solicitudes_usuarios": solicitudes_usuarios
		}
		with open(ESTADO_ARCHIVO, "w") as archivo:
			json.dump(estado, archivo)
		print("Estado guardado en estado_servidor.json")
	except IOError as e:
		print(f"Error al guardar el estado: {e}")

def cargar_estado():
	global taxis_registrados, solicitudes_usuarios
	if os.path.exists(ESTADO_ARCHIVO):
		try:
			with open(ESTADO_ARCHIVO, "r") as archivo:
				estado = json.load(archivo)
				taxis_registrados = estado.get("taxis_registrados", {})
				solicitudes_usuarios = estado.get("solicitudes_usuarios", [])
				print("Estado cargado desde estado_servidor.json")
		except (IOError, json.JSONDecodeError) as e:
			print(f"Error al cargar el estado: {e}. Iniciando desde cero.")
			taxis_registrados = {}
			solicitudes_usuarios = []
	else:
		print("No se encontró estado previo. Iniciando desde cero.")


# Función para calcular la distancia euclidiana entre dos puntos
def calcular_distancia(x1, y1, x2, y2):
	return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

# Funciones de Negociación y Roles
def iniciar_negociacion():
	"""Determina si este servidor será el principal o el respaldo."""
	global ROL
	context = zmq.Context()
	socket = context.socket(zmq.REQ)
	socket.setsockopt(zmq.RCVTIMEO, 2000)  # Espera de 2 segundos
	socket.connect(f"tcp://localhost:{DISCOVERY_PORT}")

	try:
		socket.send_string("¿Hay un principal?")
		respuesta = socket.recv_string()
		if respuesta == "Sí":
			ROL = "respaldo"
		else:
			ROL = "principal"
	except zmq.error.Again:
		# Si no hay respuesta, asume que eres el primero
		ROL = "principal"

	socket.close()
	context.term()

def publicar_presencia():
	"""El principal anuncia su presencia periódicamente."""
	context = zmq.Context()
	socket = context.socket(zmq.REP)
	socket.bind(f"tcp://*:{DISCOVERY_PORT}")

	while True:
		mensaje = socket.recv_string()
		if mensaje == "¿Hay un principal?":
			socket.send_string("Sí")
		else:
			socket.send_string("Desconocido")

# Funciones de Sincronización de Estado
def sincronizar_estado_principal():
	"""El principal envía el estado a los respaldos."""
	context = zmq.Context()
	socket = context.socket(zmq.PUSH)
	socket.bind(f"tcp://*:{ESTADO_SYNC_PORT}")

	while True:
		estado = {"taxis": taxis_registrados, "solicitudes": solicitudes_usuarios}
		socket.send_json(estado)
		time.sleep(2)  # Enviar cada 2 segundos

def recibir_estado_respaldo():
	"""El respaldo escucha y guarda el estado del principal."""
	context = zmq.Context()
	socket = context.socket(zmq.PULL)
	socket.connect(f"tcp://localhost:{ESTADO_SYNC_PORT}")

	global taxis_registrados, solicitudes_usuarios
	while True:
		estado = socket.recv_json()
		with lock:
			taxis_registrados = estado["taxis"]
			solicitudes_usuarios = estado["solicitudes"]
		print(f"Estado sincronizado: {estado}")

# Funciones de Health-Check
def health_check_respaldo():
	"""El respaldo verifica si el principal sigue activo."""
	context = zmq.Context()
	socket = context.socket(zmq.REQ)
	socket.connect(f"tcp://localhost:{HEALTH_CHECK_PORT}")

	while True:
		try:
			socket.send_string("ping")
			respuesta = socket.recv_string()
			if respuesta != "pong":
				raise Exception("Respuesta inesperada")
		except:
			print("El servidor principal ha fallado. Asumiendo control.")
			with lock:
				taxis_registrados.clear()  # Opcional: limpiar estado temporal no sincronizado
				solicitudes_usuarios.clear()
			iniciar_como_principal()
			break
		time.sleep(5)

def responder_health_check():
	"""El principal responde al health-check del respaldo."""
	context = zmq.Context()
	socket = context.socket(zmq.REP)
	socket.bind(f"tcp://*:{HEALTH_CHECK_PORT}")

	while True:
		mensaje = socket.recv_string()
		if mensaje == "ping":
			socket.send_string("pong")

# Funciones de Manejo de Posiciones y Solicitudes
def recibir_posiciones():
	"""Recibe las posiciones actualizadas de los taxis."""
	context = zmq.Context()
	socket = context.socket(zmq.SUB)
	socket.bind(f"tcp://*:{TAXI_POSITION_PORT}")
	socket.setsockopt_string(zmq.SUBSCRIBE, "")

	while True:
		mensaje = socket.recv_string()
		id_taxi, posicion = mensaje.split(":")
		posicion = tuple(map(int, posicion.strip("()").split(",")))

		with lock:
			taxis_registrados[id_taxi] = posicion
			guardar_estado()

		print(f"Posición actualizada - Taxi {id_taxi}: {posicion}")
		
def recibir_solicitudes():
	"""Recibe solicitudes de usuarios y asigna taxis."""
	context = zmq.Context()
	socket = context.socket(zmq.REP)
	socket.bind(f"tcp://*:{USER_REQUEST_PORT}")

	while True:
		mensaje = socket.recv_string()
		solicitud = json.loads(mensaje)

		id_usuario = solicitud["id_usuario"]
		x_usuario, y_usuario = solicitud["x"], solicitud["y"]

		print(f"Solicitud recibida - Usuario {id_usuario}: ({x_usuario}, {y_usuario})")

		# Inicia el cronómetro para medir el tiempo de respuesta
		tiempo_inicio = time.time()

		with lock:
			if not taxis_registrados:
				# No hay taxis disponibles
				respuesta = {"status": "rechazado", "mensaje": "No hay taxis disponibles."}
				guardar_historial(id_usuario, None, "rechazado", x_usuario, y_usuario)
			else:
				# Buscar el taxi más cercano
				taxi_asignado = None
				distancia_minima = float("inf")

				for id_taxi, posicion in taxis_registrados.items():
					distancia = calcular_distancia(x_usuario, y_usuario, posicion[0], posicion[1])
					if distancia < distancia_minima:
						distancia_minima = distancia
						taxi_asignado = id_taxi

				if taxi_asignado:
					# Asignar taxi
					respuesta = {"status": "asignado", "taxi_id": taxi_asignado}
					del taxis_registrados[taxi_asignado]
					guardar_estado()
					guardar_historial(id_usuario, taxi_asignado, "exitoso", x_usuario, y_usuario)
				else:
					# No se pudo asignar taxi
					respuesta = {"status": "rechazado", "mensaje": "No hay taxis disponibles."}
					guardar_historial(id_usuario, None, "rechazado", x_usuario, y_usuario)

		# Calcular tiempo de respuesta
		tiempo_respuesta = time.time() - tiempo_inicio
		metricas["tiempos_respuesta"].append(tiempo_respuesta)

		# Actualizar métricas
		if respuesta["status"] == "asignado":
			metricas["servicios_exitosos"] += 1
		else:
			metricas["servicios_rechazados"] += 1

		guardar_metricas()

		# Enviar respuesta al cliente
		socket.send_json(respuesta)


def asignar_servicio():
	context = zmq.Context()
	socket = context.socket(zmq.PUB)
	socket.bind(f"tcp://*:{TAXI_ASSIGN_PORT}")

	while True:
		with lock:
			if not solicitudes_usuarios:
				print("No hay solicitudes pendientes.")
				time.sleep(1)
				continue

			solicitud = solicitudes_usuarios.pop(0)
			id_usuario = solicitud["id_usuario"]
			taxi_asignado = solicitud.get("taxi_id")

			if taxi_asignado:
				mensaje = f"{taxi_asignado}:asignado"
				socket.send_string(mensaje)
				print(f"Taxi {taxi_asignado} asignado al usuario {id_usuario}.")
			else:
				print(f"No se pudo asignar un taxi para el usuario {id_usuario}.")
		time.sleep(1)

HISTORIAL_ARCHIVO = "historial_servidor.json"
historial = []

def guardar_historial(usuario_id, taxi_id, estado, x_usuario, y_usuario):
	"""Guarda una entrada de historial en el archivo JSON."""
	registro = {
		"usuario_id": usuario_id,
		"taxi_id": taxi_id,
		"estado": estado,
		"posicion_usuario": (x_usuario, y_usuario),
		"timestamp": time.time()
	}
	historial.append(registro)
	try:
		with open(HISTORIAL_ARCHIVO, "w") as archivo:
			json.dump(historial, archivo, indent=4)
		print(f"Historial actualizado: {registro}")
	except IOError as e:
		print(f"Error al guardar historial: {e}")

def cargar_historial():
	"""Carga el historial del archivo JSON si existe."""
	global historial
	if os.path.exists(HISTORIAL_ARCHIVO):
		try:
			with open(HISTORIAL_ARCHIVO, "r") as archivo:
				historial = json.load(archivo)
				print("Historial cargado desde historial_servidor.json")
		except (IOError, json.JSONDecodeError) as e:
			print(f"Error al cargar historial: {e}. Iniciando desde cero.")


METRICAS_ARCHIVO = "metricas_servidor.json"
metricas = {
	"tiempos_respuesta": [],
	"servicios_exitosos": 0,
	"servicios_rechazados": 0
}

def guardar_metricas():
	"""Guarda las métricas en un archivo JSON."""
	try:
		with open(METRICAS_ARCHIVO, "w") as archivo:
			json.dump(metricas, archivo, indent=4)
		print("Métricas actualizadas en metricas_servidor.json")
	except IOError as e:
		print(f"Error al guardar métricas: {e}")

def cargar_metricas():
	"""Carga las métricas de un archivo JSON si existe."""
	global metricas
	if os.path.exists(METRICAS_ARCHIVO):
		try:
			with open(METRICAS_ARCHIVO, "r") as archivo:
				metricas = json.load(archivo)
				print("Métricas cargadas desde metricas_servidor.json")
		except (IOError, json.JSONDecodeError) as e:
			print(f"Error al cargar métricas: {e}. Iniciando desde cero.")



# Inicialización de Roles
def iniciar_como_principal():
	"""Inicia las funciones del principal."""
	print("Este servidor es el PRINCIPAL.")
	threading.Thread(target=publicar_presencia).start()
	threading.Thread(target=sincronizar_estado_principal).start()
	threading.Thread(target=responder_health_check).start()
	threading.Thread(target=recibir_posiciones).start()
	threading.Thread(target=recibir_solicitudes).start()
	threading.Thread(target=asignar_servicio).start()
	threading.Thread(target=guardar_estado_periodicamente).start()  # Guardar estado

def iniciar_como_respaldo():
	"""Inicia las funciones del respaldo."""
	print("Este servidor es el RESPALDO.")
	threading.Thread(target=recibir_estado_respaldo).start()
	threading.Thread(target=health_check_respaldo).start()
	
def guardar_estado_periodicamente(intervalo=5):
	"""Guarda el estado en un archivo JSON cada 'intervalo' segundos."""
	while True:
		with lock:
			guardar_estado()
		time.sleep(intervalo)


if __name__ == "__main__":
	cargar_estado()     # Carga el estado de taxis y solicitudes
	cargar_historial()  # Carga el historial de asignaciones
	cargar_metricas()   # Carga las métricas de rendimiento
	iniciar_negociacion()

	if ROL == "principal":
		iniciar_como_principal()
	elif ROL == "respaldo":
		iniciar_como_respaldo()
	else:
		print("Error al determinar el rol. Terminando.")
		sys.exit(1)
