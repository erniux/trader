from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Configuración de Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trader.settings')
app = Celery('trader')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descubre tareas automáticamente en todas las apps
app.autodiscover_tasks()
