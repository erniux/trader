from __future__ import absolute_import, unicode_literals
import os
from trader.celery import Celery

# Establece la configuración de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trader.settings')

app = Celery('trader')

# Configuración de Celery usando settings de Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descubre tasks en apps registradas
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
