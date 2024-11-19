import zmq
import sys
import threading
import time
import random
import json

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
        respuesta = socket.recv_string()
        tiempo_respuesta = time.time() - tiempo_inicio

        if respuesta == "ASIGNADO":
            print(f"Usuario {id_usuario} recibió un taxi. Tiempo de respuesta: {tiempo_respuesta:.2f} segundos.")
            with lock:
                respuestas_exitosas.append(id_usuario)
        else:
            print(f"Usuario {id_usuario} no recibió un taxi. Respuesta: {respuesta}.")
            with lock:
                respuestas_fallidas.append(id_usuario)
    except zmq.error.Again:
        print(f"Usuario {id_usuario} no recibió respuesta del servidor (timeout).")
        with lock:
            respuestas_fallidas.append(id_usuario)
    finally:
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
    print(f"Resultados finales:")
    print(f"Respuestas exitosas: {len(respuestas_exitosas)}")
    print(f"Respuestas fallidas: {len(respuestas_fallidas)}")

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
respuestas_exitosas = []
respuestas_fallidas = []
lock = threading.Lock()

# Iniciar el generador de usuarios
if __name__ == "__main__":
    generador_usuarios(Y, archivo_coordenadas)
