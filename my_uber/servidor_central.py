# server.py

import zmq
import threading
import time
import json
import math
import os

# Configuración de ZeroMQ

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5557

# Puerto para recepción de posiciones de taxis
TAXI_POSITION_PORT = 5555

# Otros puertos
DISCOVERY_PORT = 5560  # Puerto para negociación inicial
ESTADO_SYNC_PORT = 5561  # Puerto para sincronización de estado
HEALTH_CHECK_PORT = 5562  # Puerto para health-check
USER_REQUEST_PORT = 5557  # Puerto para solicitudes de usuarios
TAXI_ASSIGN_PORT = 5556  # Puerto para asignaciones de taxis

# Estado global
taxis_registrados = {}  # ID -> (x, y)
solicitudes_usuarios = []  # Solicitudes pendientes
ROL = None  # Rol del servidor (principal o respaldo)
lock = threading.Lock()  # Lock para acceso concurrente al estado

print("=== INICIO DEL SERVIDOR ===", flush=True)
print(f"Rol actual del servidor: {ROL}", flush=True)
print(f"Taxis registrados: {taxis_registrados}", flush=True)
print(f"Solicitudes de usuarios: {solicitudes_usuarios}", flush=True)

# Archivo para guardar el estado
ESTADO_ARCHIVO = "estado_servidor.json"

# Crear un único contexto de ZeroMQ global
context = zmq.Context()

# Definición de cargar_estado
def cargar_estado():
    global taxis_registrados, solicitudes_usuarios
    print("Cargando estado previo...", flush=True)
    try:
        with open(ESTADO_ARCHIVO, "r") as archivo:
            estado = json.load(archivo)
        taxis_registrados = estado.get("taxis", {})
        solicitudes_usuarios = estado.get("solicitudes", [])
        print("Estado previo cargado exitosamente.", flush=True)
        print(f"Taxis registrados después de cargar: {taxis_registrados}", flush=True)
        print(f"Solicitudes de usuarios después de cargar: {solicitudes_usuarios}", flush=True)
    except FileNotFoundError:
        print("No se encontró estado previo. Iniciando desde cero.", flush=True)
    except json.JSONDecodeError as e:
        print(f"Error al decodificar el archivo de estado: {e}. Iniciando desde cero.", flush=True)
    except Exception as e:
        print(f"Error inesperado al cargar el estado: {e}. Iniciando desde cero.", flush=True)

def guardar_estado():
    print("Guardando estado actual...", flush=True)
    try:
        estado = {
            "taxis": taxis_registrados,
            "solicitudes": solicitudes_usuarios
        }
        with open(ESTADO_ARCHIVO, "w") as archivo:
            json.dump(estado, archivo, indent=4)
        print("Estado guardado en estado_servidor.json exitosamente.", flush=True)
    except IOError as e:
        print(f"Error al guardar el estado: {e}", flush=True)

# Función para calcular la distancia euclidiana entre dos puntos
def calcular_distancia(x1, y1, x2, y2):
    distancia = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    print(f"Calculando distancia entre ({x1}, {y1}) y ({x2}, {y2}): {distancia}", flush=True)
    return distancia

# Funciones de Negociación y Roles
def iniciar_negociacion():
    print("Iniciando negociación de roles...", flush=True)
    global ROL
    """Determina si este servidor será el principal o el respaldo."""
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.RCVTIMEO, 2000)  # Espera de 2 segundos
    socket.connect(f"tcp://localhost:{DISCOVERY_PORT}")
    print(f"Conectado al puerto de descubrimiento en tcp://localhost:{DISCOVERY_PORT}", flush=True)

    try:
        print("Enviando solicitud de principal...", flush=True)
        socket.send_string("¿Hay un principal?")
        print("Solicitud enviada. Esperando respuesta...", flush=True)
        respuesta = socket.recv_string()
        print(f"Respuesta recibida: {respuesta}", flush=True)
        if respuesta == "Sí":
            print("Se confirmó que ya existe un servidor principal.", flush=True)
            ROL = "respaldo"
            print("Asignado rol: RESPALDO", flush=True)
        else:
            print("No se encontró un servidor principal.", flush=True)
            ROL = "principal"
            print("Asignado rol: PRINCIPAL", flush=True)
    except zmq.error.Again as e:
        print(f"Error de tiempo de espera en la comunicación: {e}", flush=True)
        # Si no hay respuesta, asume que eres el primero
        ROL = "principal"
        print("Asumiendo rol principal por falta de respuesta.", flush=True)
    except Exception as e:
        print(f"Error inesperado durante la negociación: {e}", flush=True)
        ROL = "principal"
        print("Asumiendo rol principal debido a un error inesperado.", flush=True)
    finally:
        print("Cerrando socket", flush=True)
        try:
            socket.close()
            print("Socket cerrado exitosamente.", flush=True)
        except Exception as e:
            print(f"Error al cerrar socket: {e}", flush=True)
        print("Cierre del socket de negociación completado.", flush=True)

def publicar_presencia():
    """El principal anuncia su presencia periódicamente."""
    print("Iniciando publicación de presencia como principal...", flush=True)
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://*:{DISCOVERY_PORT}")
    print(f"Servidor principal escuchando en tcp://*:{DISCOVERY_PORT}", flush=True)

    while True:
        try:
            print("Esperando solicitudes de presencia...", flush=True)
            mensaje = socket.recv_string()
            print(f"Mensaje recibido en publicación de presencia: {mensaje}", flush=True)
            if mensaje == "¿Hay un principal?":
                print("Confirmando presencia como principal.", flush=True)
                socket.send_string("Sí")
            else:
                print("Mensaje desconocido recibido en publicación de presencia.", flush=True)
                socket.send_string("Desconocido")
        except Exception as e:
            print(f"Error en publicar_presencia: {e}", flush=True)
            break

# Funciones de Sincronización de Estado
def sincronizar_estado_principal():
    """El principal envía el estado a los respaldos."""
    print("Iniciando sincronización de estado como principal...", flush=True)
    socket = context.socket(zmq.PUSH)
    socket.bind(f"tcp://*:{ESTADO_SYNC_PORT}")
    print(f"Servidor principal enviando estado a tcp://*:{ESTADO_SYNC_PORT}", flush=True)

    while True:
        try:
            estado = {"taxis": taxis_registrados, "solicitudes": solicitudes_usuarios}
            print(f"Enviando estado sincronizado: {estado}", flush=True)
            socket.send_json(estado)
            time.sleep(2)  # Enviar cada 2 segundos
        except Exception as e:
            print(f"Error al sincronizar estado: {e}", flush=True)
            break

def recibir_estado_respaldo():
    """El respaldo escucha y guarda el estado del principal."""
    print("Iniciando recepción de estado como respaldo...", flush=True)
    socket = context.socket(zmq.PULL)
    socket.connect(f"tcp://localhost:{ESTADO_SYNC_PORT}")
    print(f"Servidor respaldo conectado a tcp://localhost:{ESTADO_SYNC_PORT} para recibir estado.", flush=True)

    global taxis_registrados, solicitudes_usuarios
    while True:
        try:
            print("Esperando estado sincronizado desde el principal...", flush=True)
            estado = socket.recv_json()
            print(f"Estado recibido para sincronizar: {estado}", flush=True)
            with lock:
                taxis_registrados = estado.get("taxis", {})
                solicitudes_usuarios = estado.get("solicitudes", [])
                print(f"Taxis registrados actualizados: {taxis_registrados}", flush=True)
                print(f"Solicitudes de usuarios actualizadas: {solicitudes_usuarios}", flush=True)
        except Exception as e:
            print(f"Error al recibir estado de respaldo: {e}", flush=True)
            break

# Funciones de Health-Check
def health_check_respaldo():
    print("Iniciando health-check como respaldo...", flush=True)
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.RCVTIMEO, 2000)  # Timeout de 2 segundos
    socket.connect(f"tcp://localhost:{HEALTH_CHECK_PORT}")
    print(f"Servidor respaldo conectado a tcp://localhost:{HEALTH_CHECK_PORT} para health-check.", flush=True)

    while True:
        try:
            print("Enviando 'ping' al servidor principal...", flush=True)
            socket.send_string("ping")
            print("Esperando respuesta 'pong' del principal...", flush=True)
            respuesta = socket.recv_string()
            print(f"Respuesta de health-check recibida: {respuesta}", flush=True)
            if respuesta != "pong":
                print("Respuesta inesperada del servidor principal.", flush=True)
                raise Exception("Respuesta inesperada en health-check.")
            else:
                print("Health-check exitoso. El principal está activo.", flush=True)
        except zmq.error.Again as e:
            print(f"Timeout o error en health-check: {e}", flush=True)
            print("El servidor principal ha fallado. Asumiendo control como principal.", flush=True)
            with lock:
                taxis_registrados.clear()
                solicitudes_usuarios.clear()
                print("Estado limpiado: taxis_registrados y solicitudes_usuarios vaciados.", flush=True)
            # Update the role before starting principal services
            global ROL
            ROL = "principal"
            print(f"Nuevo rol asignado: {ROL}", flush=True)
            iniciar_como_principal()
            break
        except Exception as e:
            print(f"Error en health_check_respaldo: {e}", flush=True)
            print("Asumiendo rol principal debido a un error en health-check.", flush=True)
            with lock:
                taxis_registrados.clear()
                solicitudes_usuarios.clear()
                print("Estado limpiado: taxis_registrados y solicitudes_usuarios vaciados.", flush=True)
            ROL = "principal"
            print(f"Nuevo rol asignado: {ROL}", flush=True)
            iniciar_como_principal()
            break
        time.sleep(2)

def responder_health_check():
    """El principal responde al health-check del respaldo."""
    print("Iniciando respuesta a health-check como principal...", flush=True)
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://*:{HEALTH_CHECK_PORT}")
    print(f"Servidor principal escuchando health-check en tcp://*:{HEALTH_CHECK_PORT}", flush=True)

    while True:
        try:
            print("Esperando 'ping' para health-check...", flush=True)
            mensaje = socket.recv_string()
            print(f"Mensaje de health-check recibido: {mensaje}", flush=True)
            if mensaje == "ping":
                print("Enviando respuesta 'pong' al health-check.", flush=True)
                socket.send_string("pong")
            else:
                print("Mensaje desconocido en health-check. Enviando 'pong' de todas formas.", flush=True)
                socket.send_string("pong")
        except Exception as e:
            print(f"Error en responder_health_check: {e}", flush=True)
            break

# Funciones de Manejo de Posiciones y Solicitudes
def recibir_posiciones():
    """Recibe las posiciones actualizadas de los taxis."""
    print("Iniciando recepción de posiciones de taxis...", flush=True)
    socket = context.socket(zmq.PULL)  # Cambiado de SUB a PULL
    socket.bind(f"tcp://*:{TAXI_POSITION_PORT}")
    print(f"Escuchando posiciones de taxis en tcp://*:{TAXI_POSITION_PORT}", flush=True)

    while True:
        try:
            print("Esperando mensaje de posición de taxi...", flush=True)
            mensaje = socket.recv_string()
            print(f"Mensaje de posición recibido: {mensaje}", flush=True)
            id_taxi, posicion = mensaje.split(":")
            posicion = tuple(map(int, posicion.strip("()").split(",")))
            print(f"Taxi ID: {id_taxi}, Nueva posición: {posicion}", flush=True)

            with lock:
                taxis_registrados[id_taxi] = posicion
                print(f"Taxis registrados actualizados: {taxis_registrados}", flush=True)
                guardar_estado()

            print(f"Posición actualizada - Taxi {id_taxi}: {posicion}", flush=True)
        except ValueError as ve:
            print(f"Error al procesar el mensaje de posición: {ve}", flush=True)
        except Exception as e:
            print(f"Error en recibir_posiciones: {e}", flush=True)
            break

def recibir_solicitudes():
    """Recibe solicitudes de usuarios y asigna taxis."""
    print("Iniciando recepción de solicitudes de usuarios...", flush=True)
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://*:{USER_REQUEST_PORT}")
    print(f"Escuchando solicitudes de usuarios en tcp://*:{USER_REQUEST_PORT}", flush=True)

    while True:
        try:
            print("Esperando solicitud de usuario...", flush=True)
            mensaje = socket.recv_string()
            print(f"Mensaje de solicitud recibido: {mensaje}", flush=True)
            solicitud = json.loads(mensaje)
            print(f"Solicitud procesada: {solicitud}", flush=True)

            id_usuario = solicitud["id_usuario"]
            x_usuario, y_usuario = solicitud["x"], solicitud["y"]

            print(f"Solicitud recibida - Usuario {id_usuario}: ({x_usuario}, {y_usuario})", flush=True)

            # Inicia el cronómetro para medir el tiempo de respuesta
            tiempo_inicio = time.time()

            with lock:
                if not taxis_registrados:
                    print("No hay taxis disponibles para asignar.", flush=True)
                    # No hay taxis disponibles
                    respuesta = {"status": "rechazado", "mensaje": "No hay taxis disponibles."}
                    guardar_historial(id_usuario, None, "rechazado", x_usuario, y_usuario)
                else:
                    print("Buscando el taxi más cercano disponible...", flush=True)
                    # Buscar el taxi más cercano
                    taxi_asignado = None
                    distancia_minima = float("inf")

                    for id_taxi, posicion in taxis_registrados.items():
                        distancia = calcular_distancia(x_usuario, y_usuario, posicion[0], posicion[1])
                        print(f"Taxi {id_taxi} - Distancia calculada: {distancia}", flush=True)
                        if distancia < distancia_minima:
                            distancia_minima = distancia
                            taxi_asignado = id_taxi
                            print(f"Nuevo taxi más cercano encontrado: {taxi_asignado} con distancia {distancia_minima}", flush=True)

                    if taxi_asignado:
                        # Asignar taxi
                        print(f"Asignando Taxi {taxi_asignado} al Usuario {id_usuario}.", flush=True)
                        respuesta = {"status": "asignado", "taxi_id": taxi_asignado}
                        del taxis_registrados[taxi_asignado]
                        print(f"Taxi {taxi_asignado} eliminado de taxis_registrados.", flush=True)
                        guardar_estado()
                        guardar_historial(id_usuario, taxi_asignado, "exitoso", x_usuario, y_usuario)
                    else:
                        # No se pudo asignar taxi
                        print("No se pudo asignar ningún taxi.", flush=True)
                        respuesta = {"status": "rechazado", "mensaje": "No hay taxis disponibles."}
                        guardar_historial(id_usuario, None, "rechazado", x_usuario, y_usuario)

            # Calcular tiempo de respuesta
            tiempo_respuesta = time.time() - tiempo_inicio
            print(f"Tiempo de respuesta para la solicitud del Usuario {id_usuario}: {tiempo_respuesta} segundos", flush=True)
            metricas["tiempos_respuesta"].append(tiempo_respuesta)
            print(f"Métricas actualizadas: {metricas}", flush=True)

            # Actualizar métricas
            if respuesta["status"] == "asignado":
                metricas["servicios_exitosos"] += 1
                print(f"Incrementando servicios exitosos: {metricas['servicios_exitosos']}", flush=True)
            else:
                metricas["servicios_rechazados"] += 1
                print(f"Incrementando servicios rechazados: {metricas['servicios_rechazados']}", flush=True)

            guardar_metricas()

            # Enviar respuesta al cliente
            print(f"Enviando respuesta al Usuario {id_usuario}: {respuesta}", flush=True)
            socket.send_json(respuesta)
        except json.JSONDecodeError as je:
            print(f"Error al decodificar la solicitud JSON: {je}", flush=True)
            respuesta = {"status": "error", "mensaje": "Solicitud JSON inválida."}
            socket.send_json(respuesta)
        except Exception as e:
            print(f"Error en recibir_solicitudes: {e}", flush=True)
            respuesta = {"status": "error", "mensaje": "Error interno del servidor."}
            socket.send_json(respuesta)

def asignar_servicio():
    print("Iniciando asignación de servicios...", flush=True)
    socket = context.socket(zmq.PUB)
    socket.bind(f"tcp://*:{TAXI_ASSIGN_PORT}")
    print(f"Publicando asignaciones de taxis en tcp://*:{TAXI_ASSIGN_PORT}", flush=True)

    while True:
        try:
            with lock:
                if not solicitudes_usuarios:
                    print("No hay solicitudes pendientes para asignar.", flush=True)
                    time.sleep(1)
                    continue

                solicitud = solicitudes_usuarios.pop(0)
                print(f"Procesando solicitud para asignar: {solicitud}", flush=True)
                id_usuario = solicitud["id_usuario"]
                taxi_asignado = solicitud.get("taxi_id")

                if taxi_asignado:
                    mensaje = f"{taxi_asignado}:asignado"
                    print(f"Enviando asignación de Taxi {taxi_asignado} al Usuario {id_usuario}. Mensaje: {mensaje}", flush=True)
                    socket.send_string(mensaje)
                else:
                    print(f"No se pudo asignar un taxi para el Usuario {id_usuario}.", flush=True)
            time.sleep(1)
        except Exception as e:
            print(f"Error en asignar_servicio: {e}", flush=True)
            break

HISTORIAL_ARCHIVO = "historial_servidor.json"
historial = []

def guardar_historial(usuario_id, taxi_id, estado, x_usuario, y_usuario):
    """Guarda una entrada de historial en el archivo JSON."""
    print(f"Guardando historial para Usuario {usuario_id}, Taxi {taxi_id}, Estado: {estado}", flush=True)
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
        print(f"Historial actualizado con registro: {registro}", flush=True)
    except IOError as e:
        print(f"Error al guardar historial: {e}", flush=True)

def cargar_historial():
    """Carga el historial del archivo JSON si existe."""
    global historial
    print("Cargando historial de asignaciones...", flush=True)
    if os.path.exists(HISTORIAL_ARCHIVO):
        try:
            with open(HISTORIAL_ARCHIVO, "r") as archivo:
                historial = json.load(archivo)
            print("Historial cargado desde historial_servidor.json", flush=True)
            print(f"Historial actual: {historial}", flush=True)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error al cargar historial: {e}. Iniciando historial vacío.", flush=True)
            historial = []
    else:
        print("No existe historial previo. Iniciando historial vacío.", flush=True)

METRICAS_ARCHIVO = "metricas_servidor.json"
metricas = {
    "tiempos_respuesta": [],
    "servicios_exitosos": 0,
    "servicios_rechazados": 0
}

def guardar_metricas():
    """Guarda las métricas en un archivo JSON."""
    print("Guardando métricas actuales...", flush=True)
    try:
        with open(METRICAS_ARCHIVO, "w") as archivo:
            json.dump(metricas, archivo, indent=4)
        print("Métricas actualizadas en metricas_servidor.json", flush=True)
    except IOError as e:
        print(f"Error al guardar métricas: {e}", flush=True)

def cargar_metricas():
    """Carga las métricas de un archivo JSON si existe."""
    global metricas
    print("Cargando métricas del servidor...", flush=True)
    if os.path.exists(METRICAS_ARCHIVO):
        try:
            with open(METRICAS_ARCHIVO, "r") as archivo:
                metricas = json.load(archivo)
            print("Métricas cargadas desde metricas_servidor.json", flush=True)
            print(f"Métricas actuales: {metricas}", flush=True)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error al cargar métricas: {e}. Iniciando métricas vacías.", flush=True)
            metricas = {
                "tiempos_respuesta": [],
                "servicios_exitosos": 0,
                "servicios_rechazados": 0
            }
    else:
        print("No existen métricas previas. Iniciando métricas vacías.", flush=True)

# Inicialización de Roles
def iniciar_como_principal():
    print("Iniciando funciones del servidor como PRINCIPAL.", flush=True)
    try:
        threading.Thread(target=publicar_presencia, daemon=True).start()
        print("Thread de publicar_presencia iniciado.", flush=True)
    except Exception as e:
        print(f"Error al iniciar thread de publicar_presencia: {e}", flush=True)
    
    try:
        threading.Thread(target=sincronizar_estado_principal, daemon=True).start()
        print("Thread de sincronizar_estado_principal iniciado.", flush=True)
    except Exception as e:
        print(f"Error al iniciar thread de sincronizar_estado_principal: {e}", flush=True)
    
    try:
        threading.Thread(target=responder_health_check, daemon=True).start()
        print("Thread de responder_health_check iniciado.", flush=True)
    except Exception as e:
        print(f"Error al iniciar thread de responder_health_check: {e}", flush=True)
    
    try:
        threading.Thread(target=recibir_posiciones, daemon=True).start()
        print("Thread de recibir_posiciones iniciado.", flush=True)
    except Exception as e:
        print(f"Error al iniciar thread de recibir_posiciones: {e}", flush=True)
    
    try:
        threading.Thread(target=recibir_solicitudes, daemon=True).start()
        print("Thread de recibir_solicitudes iniciado.", flush=True)
    except Exception as e:
        print(f"Error al iniciar thread de recibir_solicitudes: {e}", flush=True)
    
    try:
        threading.Thread(target=asignar_servicio, daemon=True).start()
        print("Thread de asignar_servicio iniciado.", flush=True)
    except Exception as e:
        print(f"Error al iniciar thread de asignar_servicio: {e}", flush=True)
    
    try:
        threading.Thread(target=guardar_estado_periodicamente, daemon=True).start()
        print("Thread de guardar_estado_periodicamente iniciado.", flush=True)
    except Exception as e:
        print(f"Error al iniciar thread de guardar_estado_periodicamente: {e}", flush=True)

def iniciar_como_respaldo():
    """Inicia las funciones del respaldo."""
    print("Iniciando funciones del servidor como RESPALDO.", flush=True)
    try:
        threading.Thread(target=recibir_estado_respaldo, daemon=True).start()
        print("Thread de recibir_estado_respaldo iniciado.", flush=True)
    except Exception as e:
        print(f"Error al iniciar thread de recibir_estado_respaldo: {e}", flush=True)
    
    try:
        threading.Thread(target=health_check_respaldo, daemon=True).start()
        print("Thread de health_check_respaldo iniciado.", flush=True)
    except Exception as e:
        print(f"Error al iniciar thread de health_check_respaldo: {e}", flush=True)

def guardar_estado_periodicamente(intervalo=5):
    """Guarda el estado en un archivo JSON cada 'intervalo' segundos."""
    print(f"Iniciando guardado periódico del estado cada {intervalo} segundos.", flush=True)
    while True:
        try:
            with lock:
                print("Guardando estado de manera periódica...", flush=True)
                guardar_estado()
            time.sleep(intervalo)
        except Exception as e:
            print(f"Error en guardar_estado_periodicamente: {e}", flush=True)
            break

if __name__ == "__main__":
    print("=== INICIANDO SERVIDOR ===", flush=True)
    cargar_estado()          # Load the state of taxis and requests
    cargar_historial()       # Load the assignment history
    cargar_metricas()        # Load performance metrics
    iniciar_negociacion()    # Perform role negotiation

    if ROL == "principal":
        iniciar_como_principal()
    elif ROL == "respaldo":
        iniciar_como_respaldo()
    else:
        print("Rol no asignado correctamente. Verifica la negociación de roles.", flush=True)

    # Keep the program running
    print(f"Rol actual del servidor: {ROL}", flush=True)
    print(f"Taxis registrados: {taxis_registrados}", flush=True)
    print(f"Solicitudes de usuarios: {solicitudes_usuarios}", flush=True)
    try:
        while True:
            time.sleep(1)  # Evita el uso intensivo de CPU
    except KeyboardInterrupt:
        print("Servidor detenido por el usuario.", flush=True)
    except Exception as e:
        print(f"Error inesperado en el ciclo principal: {e}", flush=True)
    finally:
        print("Cerrando servidor de manera segura.", flush=True)
        try:
            context.term()
            print("Contexto global terminado exitosamente.", flush=True)
        except Exception as e:
            print(f"Error al terminar el contexto global: {e}", flush=True)
