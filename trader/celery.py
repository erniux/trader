from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# ─── Configuración base de Django ───
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trader.settings")

# ─── Instancia Celery ───
celery_app = Celery("trader")

# Toma configuración desde settings.py → claves prefijadas con CELERY_
celery_app.config_from_object("django.conf:settings", namespace="CELERY")

# Descubre tasks.py en todas las apps instaladas
celery_app.autodiscover_tasks()

@celery_app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")

# Para facilitar importaciones:  from trader.celery import celery_app
__all__ = ("celery_app",)
