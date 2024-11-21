# run_simulations.py

import subprocess
import sys
import time
import os
import json
import random
import matplotlib.pyplot as plt
from threading import Thread
import psutil  # Para monitorear métricas del sistema

def run_server(simulation_dir):
    """
    Ejecuta el servidor central en el directorio especificado.
    """
    server_log_path = os.path.join(simulation_dir, "server.log")
    with open(server_log_path, "w") as server_log:
        server_process = subprocess.Popen(
            ["python3", "server.py"],
            cwd=simulation_dir,
            stdout=server_log,
            stderr=server_log
        )
    print(f"Servidor lanzado en {simulation_dir} con PID {server_process.pid}")
    return server_process

def run_taxis(simulation_dir, numero_taxis, N, M, velocidad):
    """
    Ejecuta múltiples instancias de taxi.py en el directorio especificado.
    """
    taxi_processes = []
    for i in range(1, numero_taxis + 1):
        id_taxi = f"taxi_{i}"
        x = random.randint(0, N - 1)
        y = random.randint(0, M - 1)
        taxi_log_path = os.path.join(simulation_dir, f"{id_taxi}.log")
        with open(taxi_log_path, "w") as taxi_log:
            comando = [
                "python3", "taxi.py",
                id_taxi,
                str(N),
                str(M),
                str(x),
                str(y),
                str(velocidad)
            ]
            proceso = subprocess.Popen(
                comando,
                cwd=simulation_dir,
                stdout=taxi_log,
                stderr=taxi_log
            )
            taxi_processes.append(proceso)
            print(f"Lanzado {id_taxi} en posición ({x}, {y}) con PID {proceso.pid}")
            time.sleep(0.05)  # Pequeña pausa para evitar sobrecarga
    return taxi_processes

def run_users(simulation_dir, numero_usuarios, N, M, archivo_coordenadas):
    """
    Ejecuta el script usuario.py con la cantidad especificada de usuarios.
    """
    user_log_path = os.path.join(simulation_dir, "users.log")
    with open(user_log_path, "w") as user_log:
        comando = [
            "python3", "usuario.py",
            str(N),
            str(M),
            str(numero_usuarios),
            archivo_coordenadas
        ]
        proceso = subprocess.Popen(
            comando,
            cwd=simulation_dir,
            stdout=user_log,
            stderr=user_log
        )
    print(f"Usuarios lanzados con PID {proceso.pid}")
    return proceso

def collect_metrics(simulation_dir):
    """
    Recopila las métricas de los archivos JSON en el directorio de simulación.
    """
    metrics = {}
    # Server metrics
    server_metrics_file = os.path.join(simulation_dir, "metricas_servidor.json")
    if os.path.exists(server_metrics_file):
        with open(server_metrics_file, "r") as f:
            metrics["server"] = json.load(f)
    else:
        metrics["server"] = {}
    
    # Taxi metrics
    taxi_metrics_file = os.path.join(simulation_dir, "metricas_taxi.json")
    if os.path.exists(taxi_metrics_file):
        with open(taxi_metrics_file, "r") as f:
            metrics["taxi"] = json.load(f)
    else:
        metrics["taxi"] = {}
    
    # User metrics
    user_metrics_file = os.path.join(simulation_dir, "estadisticas_usuario.json")
    if os.path.exists(user_metrics_file):
        with open(user_metrics_file, "r") as f:
            metrics["user"] = json.load(f)
    else:
        metrics["user"] = {}
    
    # Historial
    historial_file = os.path.join(simulation_dir, "historial_servidor.json")
    if os.path.exists(historial_file):
        with open(historial_file, "r") as f:
            metrics["historial"] = json.load(f)
    else:
        metrics["historial"] = []
    
    # System metrics
    system_metrics_file = os.path.join(simulation_dir, "system_metrics.json")
    if os.path.exists(system_metrics_file):
        with open(system_metrics_file, "r") as f:
            metrics["system"] = json.load(f)
    else:
        metrics["system"] = {}
    
    return metrics

def save_metrics(results, output_file="results.json"):
    """
    Guarda todos los resultados de las simulaciones en un archivo JSON.
    """
    with open(output_file, "w") as f:
        json.dump(results, f, indent=4)
    print(f"Métricas guardadas en {output_file}")

def monitorear_sistema(simulation_dir, duracion, intervalo=1):
    """
    Monitorea el uso de CPU y memoria durante la simulación.
    """
    metrics = {"timestamp": [], "cpu_percent": [], "memory_percent": []}
    start_time = time.time()
    while (time.time() - start_time) < duracion:
        metrics["timestamp"].append(time.time() - start_time)
        metrics["cpu_percent"].append(psutil.cpu_percent(interval=None))
        metrics["memory_percent"].append(psutil.virtual_memory().percent)
        time.sleep(intervalo)
    # Guardar las métricas
    system_metrics_file = os.path.join(simulation_dir, "system_metrics.json")
    with open(system_metrics_file, "w") as f:
        json.dump(metrics, f, indent=4)
    print(f"Métricas de sistema guardadas en {system_metrics_file}")

def generar_graficas(resultados):
    """
    Genera gráficas basadas en los resultados de las simulaciones.
    """
    # Asegurarse de tener resultados
    if not resultados:
        print("No hay resultados para generar gráficas.")
        return
    
    # Ejemplo 1: Tiempo de Respuesta Promedio vs. Número de Usuarios para cada Número de Taxis
    plt.figure(figsize=(10, 6))
    taxis_unique = sorted(set(r["numero_taxis"] for r in resultados))
    for numero_taxis in taxis_unique:
        usuarios = []
        tiempo_respuesta = []
        for r in resultados:
            if r["numero_taxis"] == numero_taxis:
                usuarios.append(r["numero_usuarios"])
                tiempos = r["metrics"]["user"].get("tiempos_respuesta", [])
                if tiempos:
                    promedio = sum(tiempos) / len(tiempos)
                else:
                    promedio = 0
                tiempo_respuesta.append(promedio)
        plt.plot(usuarios, tiempo_respuesta, marker='o', label=f"{numero_taxis} taxis")
    plt.xlabel("Número de Usuarios")
    plt.ylabel("Tiempo de Respuesta Promedio (s)")
    plt.title("Tiempo de Respuesta Promedio vs. Número de Usuarios")
    plt.legend()
    plt.grid(True)
    plt.savefig("tiempo_respuesta_vs_usuarios.png")
    plt.show()

    # Ejemplo 2: Solicitudes Exitosas y Fallidas vs. Número de Usuarios para cada Número de Taxis
    plt.figure(figsize=(10, 6))
    for numero_taxis in taxis_unique:
        usuarios = []
        exitosas = []
        fallidas = []
        for r in resultados:
            if r["numero_taxis"] == numero_taxis:
                usuarios.append(r["numero_usuarios"])
                user_metrics = r["metrics"]["user"]
                exitosas.append(user_metrics.get("solicitudes_exitosas", 0))
                fallidas.append(user_metrics.get("solicitudes_fallidas", 0))
        plt.plot(usuarios, exitosas, marker='o', label=f"Exitosas - {numero_taxis} taxis")
        plt.plot(usuarios, fallidas, marker='x', label=f"Fallidas - {numero_taxis} taxis")
    plt.xlabel("Número de Usuarios")
    plt.ylabel("Número de Solicitudes")
    plt.title("Solicitudes Exitosas y Fallidas vs. Número de Usuarios")
    plt.legend()
    plt.grid(True)
    plt.savefig("solicitudes_vs_usuarios.png")
    plt.show()

    # Ejemplo 3: Uso de CPU Promedio vs. Número de Usuarios para cada Número de Taxis
    plt.figure(figsize=(10, 6))
    for numero_taxis in taxis_unique:
        usuarios = []
        cpu_promedio = []
        for r in resultados:
            if r["numero_taxis"] == numero_taxis:
                usuarios.append(r["numero_usuarios"])
                system_metrics = r["metrics"].get("system", {})
                cpu = system_metrics.get("cpu_percent", [])
                if cpu:
                    promedio = sum(cpu) / len(cpu)
                else:
                    promedio = 0
                cpu_promedio.append(promedio)
        plt.plot(usuarios, cpu_promedio, marker='o', label=f"{numero_taxis} taxis")
    plt.xlabel("Número de Usuarios")
    plt.ylabel("Uso de CPU Promedio (%)")
    plt.title("Uso de CPU Promedio vs. Número de Usuarios")
    plt.legend()
    plt.grid(True)
    plt.savefig("cpu_vs_usuarios.png")
    plt.show()

    # Ejemplo 4: Uso de Memoria Promedio vs. Número de Usuarios para cada Número de Taxis
    plt.figure(figsize=(10, 6))
    for numero_taxis in taxis_unique:
        usuarios = []
        memoria_promedio = []
        for r in resultados:
            if r["numero_taxis"] == numero_taxis:
                usuarios.append(r["numero_usuarios"])
                system_metrics = r["metrics"].get("system", {})
                memoria = system_metrics.get("memory_percent", [])
                if memoria:
                    promedio = sum(memoria) / len(memoria)
                else:
                    promedio = 0
                memoria_promedio.append(promedio)
        plt.plot(usuarios, memoria_promedio, marker='o', label=f"{numero_taxis} taxis")
    plt.xlabel("Número de Usuarios")
    plt.ylabel("Uso de Memoria Promedio (%)")
    plt.title("Uso de Memoria Promedio vs. Número de Usuarios")
    plt.legend()
    plt.grid(True)
    plt.savefig("memoria_vs_usuarios.png")
    plt.show()

    print("Gráficas generadas y guardadas exitosamente.")

def run_simulation(simulation_id, numero_taxis, numero_usuarios, N, M, velocidad, archivo_coordenadas):
    """
    Ejecuta una simulación completa.
    """
    print(f"=== Iniciando simulación {simulation_id} ===")
    simulation_dir = os.path.join("simulations", simulation_id)
    os.makedirs(simulation_dir, exist_ok=True)  # Asegurar que el directorio existe

    # Ejecutar el servidor
    server_process = run_server(simulation_dir)
    print(f"Servidor lanzado para {simulation_id} con PID {server_process.pid}")
    time.sleep(5)  # Esperar a que el servidor se inicie correctamente

    # Ejecutar taxis
    taxi_processes = run_taxis(simulation_dir, numero_taxis, N, M, velocidad)

    # Ejecutar usuarios
    user_process = run_users(simulation_dir, numero_usuarios, N, M, archivo_coordenadas)
    print(f"Usuarios lanzados para {simulation_id} con PID {user_process.pid}")

    # Iniciar monitoreo del sistema en un hilo separado
    duracion_simulacion = 60  # Duración en segundos (ajusta según tus necesidades)
    monitoreo_thread = Thread(target=monitorear_sistema, args=(simulation_dir, duracion_simulacion))
    monitoreo_thread.start()

    # Esperar a que los usuarios terminen
    user_process.wait()
    print(f"Usuarios completados para {simulation_id}")

    # Esperar a que el monitoreo termine
    monitoreo_thread.join()
    print(f"Monitoreo de sistema completado para {simulation_id}")

    # Terminar los procesos de taxis y servidor
    for proceso in taxi_processes:
        proceso.terminate()
        print(f"Proceso de {proceso.args[2]} terminado.")
    server_process.terminate()
    print(f"Proceso de servidor {server_process.pid} terminado.")

    # Recopilar métricas
    metrics = collect_metrics(simulation_dir)
    print(f"Métricas recopiladas para {simulation_id}")

    return {
        "simulation_id": simulation_id,
        "numero_taxis": numero_taxis,
        "numero_usuarios": numero_usuarios,
        "metrics": metrics
    }

def main():
    # Configuraciones de simulaciones
    taxis_list = [10, 50, 100]      # Ejemplos de números de taxis
    users_list = [100, 500, 1000]   # Ejemplos de números de usuarios
    N = 10                          # Tamaño de la cuadrícula (filas) ajustado a 10
    M = 10                          # Tamaño de la cuadrícula (columnas) ajustado a 10
    velocidad = 5                   # Velocidad de los taxis
    archivo_coordenadas = "archivo_usuarios.txt"  # Archivo con coordenadas de usuarios

    os.makedirs("simulations", exist_ok=True)

    resultados = []
    for numero_taxis in taxis_list:
        for numero_usuarios in users_list:
            simulation_id = f"taxis_{numero_taxis}_users_{numero_usuarios}"
            print(f"\n=== Ejecutando Simulación: {simulation_id} ===")
            
            # Crear archivo temporal con las primeras 'numero_usuarios' coordenadas
            simulation_dir = os.path.join("simulations", simulation_id)
            os.makedirs(simulation_dir, exist_ok=True)  # Crear el directorio antes de abrir el archivo
            
            archivo_temp = os.path.join(simulation_dir, "archivo_temp_usuarios.txt")
            with open(archivo_coordenadas, 'r') as original, open(archivo_temp, 'w') as temp:
                for _ in range(numero_usuarios):
                    linea = original.readline()
                    if not linea:
                        # Si no hay suficientes líneas, generar coordenadas aleatorias
                        x = random.randint(0, N - 1)
                        y = random.randint(0, M - 1)
                        temp.write(f"{x},{y}\n")
                    else:
                        temp.write(linea)
            
            # Ejecutar la simulación
            resultado = run_simulation(simulation_id, numero_taxis, numero_usuarios, N, M, velocidad, archivo_temp)
            resultados.append(resultado)
            save_metrics(resultados, os.path.join("simulations", "results.json"))
            
            # Eliminar el archivo temporal después de la simulación
            os.remove(archivo_temp)
            print(f"Simulación {simulation_id} completada.\n")

    # Generar gráficas después de todas las simulaciones
    generar_graficas(resultados)

if __name__ == "__main__":
    main()
