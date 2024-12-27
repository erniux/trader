### CONFIGURACION DEL PROYECTO

##1. Configuración del Proyecto
a. Crea un entorno Dockerizado:

Django: Para la API y la lógica de negocios.
Celery: Para tareas asíncronas (como consultas a la API de intercambio).
Redis: Como backend para Celery.
PostgreSQL: Para almacenar datos (opcional, según los requisitos).


##2. Construcción del Sistema
-a. Django:
Configura un proyecto básico de Django.
Crea una aplicación específica, por ejemplo, arbitraje_app:
Modelos: Para guardar pares de mercado, precios históricos, y logs de transacciones.
Vistas/APIs: Para consultar las oportunidades detectadas.

-b. Celery:
Integra Celery en Django.
Crea tareas asíncronas para:
Consultar los precios de la API del intercambio (e.g., Binance).
Realizar cálculos de arbitraje.
Registrar oportunidades en la base de datos.

-c. Docker:
Configura un contenedor para Django.
Añade servicios para Redis (backend de Celery) y PostgreSQL (opcional).
Usa Docker Compose para orquestar todo.
d. Automatización del arbitraje:
Define funciones en Python para:
Calcular rutas de arbitraje.
Comparar precios en tiempo real.
Integra estas funciones en las tareas de Celery.

##3. Iteración del Desarrollo
-Primera Fase: API básica con Django y tareas simples en Celery.
-Segunda Fase: Conexión a una API real como Binance.
-Tercera Fase: Simulador para probar rutas de arbitraje.
-Cuarta Fase: Ejecución automatizada de operaciones (con cuidado).

### Comandos Importantes:
#Reiniciar la base de datos:
docker exec -it postgres_db psql -U postgres -d trader
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;

