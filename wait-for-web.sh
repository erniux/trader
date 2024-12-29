#!/bin/bash
set -e

host="$1"
shift
cmd="$@"

echo "Esperando a que el servicio web esté listo en $host..."

until curl -s http://$host:8000/health/ > /dev/null; do
    >&2 echo "El servicio web no está listo. Esperando..."
    sleep 5
done

echo "El servicio web está listo. Ejecutando el siguiente comando: $cmd"
exec $cmd
