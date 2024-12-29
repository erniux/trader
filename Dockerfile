FROM python:3.10-slim

# Configuración del entorno
ENV PYTHONUNBUFFERED=1


# Instalar dependencias de sistema, incluido curl
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    curl \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo y copiar archivos importantes
WORKDIR /trader
COPY requirements.txt /trader/requirements.txt
COPY entrypoint.sh /trader/entrypoint.sh
COPY wait-for-web.sh /trader/wait-for-web.sh


# Configurar el PYTHONPATH
ENV PYTHONPATH=/trader
ENV PYTHONPATH="/trader:${PYTHONPATH}"


# Instalar dependencias de Python
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --upgrade python-binance


# Dar permisos de ejecución a los scripts
RUN chmod +x /trader/entrypoint.sh /trader/wait-for-web.sh

# Configurar el entrypoint
ENTRYPOINT ["sh", "/trader/entrypoint.sh"]

# Comando por defecto
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

COPY . /trader/

