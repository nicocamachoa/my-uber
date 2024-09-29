# My-Uber

Este proyecto simula un sistema distribuido tipo Uber con taxis que envían sus posiciones a un servidor central y reciben asignaciones de servicio.

## Estructura del Proyecto

my_uber/ ├── servidor_central.py ├── taxi.py └── README.md

markdown


## Preparación del Entorno

1. **Requisitos de Python**
   - Asegúrate de tener Python 3.6 o superior instalado en tu sistema.

2. **Instalar ZeroMQ**
   - Necesitarás instalar la librería `pyzmq` para la comunicación entre procesos:

pip install pyzmq

bash


## Paso 1: Configuración del Proyecto

1. **Crear la carpeta del proyecto**

```bash
mkdir my_uber
cd my_uber

    Clonar los archivos del proyecto
        Descarga servidor_central.py y taxi.py a esta carpeta.

Paso 2: Ejecutar el Servidor Central

El servidor central debe ser ejecutado en una máquina que pueda recibir conexiones de los taxis.

bash

python servidor_central.py

Esto abrirá dos puertos:

    5555 para recibir posiciones de taxis.
    5556 para enviar asignaciones de servicio.

Paso 3: Configurar y Ejecutar los Taxis
En la misma máquina o una diferente

    Editar taxi.py si el servidor central está en otra máquina:
        Cambia SERVER_IP en taxi.py a la dirección IP de la máquina donde está corriendo el servidor central.

    Ejecutar taxis

    Abre una nueva terminal por cada taxi que quieras ejecutar y usa el siguiente comando:

    bash

python taxi.py <ID> <N> <M> <X> <Y> <Velocidad>

Donde:

    <ID>: Número identificador del taxi.
    <N>: Tamaño de la cuadrícula (número de filas).
    <M>: Tamaño de la cuadrícula (número de columnas).
    <X>: Posición inicial del taxi en X (columna).
    <Y>: Posición inicial del taxi en Y (fila).
    <Velocidad>: Velocidad de movimiento del taxi (1, 2, o 4 km/h).

Ejemplo:

bash

    python taxi.py 1 100 100 10 10 2

    Esto ejecutará un taxi con:
        ID = 1
        Cuadrícula de 100x100
        Posición inicial en (10, 10)
        Velocidad de 2 km/h (se mueve cada 30 minutos del sistema, equivalente a 15 segundos de tiempo real).

Paso 4: Ejecutar el Sistema en Dos Computadoras
En la Máquina del Servidor (e.g., IP 192.168.1.10)

    Modifica TAXI_POSITION_IP y TAXI_ASSIGN_IP en servidor_central.py para que coincidan con la IP de la máquina del servidor o usa "0.0.0.0" para aceptar conexiones de cualquier IP.
    Ejecuta el servidor central:

bash

python servidor_central.py

En la Máquina del Taxi

    Cambia la variable SERVER_IP en taxi.py a la IP de la máquina del servidor (e.g., 192.168.1.10).
    Ejecuta uno o más taxis:

bash

python taxi.py <ID> <N> <M> <X> <Y> <Velocidad>

Ejemplo:

bash

python taxi.py 1 100 100 10 10 2

Notas Adicionales

    Cada taxi puede hacer un máximo de 3 servicios diarios. Una vez completados, el taxi finalizará su operación.
    La cuadrícula de la ciudad tiene un tamaño N x M, y cada taxi tiene una velocidad que define cuánto se mueve por unidad de tiempo.
    Asegúrate de ejecutar el servidor central antes de los taxis para que las posiciones y servicios puedan ser correctamente gestionados.