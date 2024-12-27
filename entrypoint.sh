#!/bin/sh

# Esperar a que la base de datos esté lista
echo "Esperando a que la base de datos esté lista..."
while ! nc -z db 5432; do
  sleep 1
done
echo "Base de datos disponible."

# Ejecutar migraciones
echo "Ejecutando makemigrations y migrate..."
python manage.py makemigrations 
python manage.py migrate 

# Crear superusuario si no existe
echo "Creando superusuario..."
python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='${DJANGO_SUPERUSER_USERNAME}').exists():
    User.objects.create_superuser(
        username='${DJANGO_SUPERUSER_USERNAME}',
        email='${DJANGO_SUPERUSER_EMAIL}',
        password='${DJANGO_SUPERUSER_PASSWORD}'
    )
EOF

# Iniciar el servidor de Django
echo "Iniciando el servidor de desarrollo..."

# Ejecutar la tarea inicial
echo "Ejecutando tarea inicial de Celery..."
python manage.py shell <<EOF
from dashboard.tasks import fetch_and_save_symbols_with_time
fetch_and_save_symbols_with_time.delay()
EOF


exec "$@"