from django.db import models
from django.utils.timezone import now

class Oportunity(models.Model):
    route=models.CharField(max_length=255)
    symbol_1=models.CharField(max_length=10)
    symbol_2=models.CharField(max_length=10)
    symbol_3=models.CharField(max_length=10)
    detected_at=models.DateTimeField(default=now())

    class Meta:
        ordering = ['-detected_at']  # Ordenar por la fecha de detección, más reciente primero

    def __str__(self):
        return self.route