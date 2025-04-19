
import os
import logging
import time
import pytz
import logging

from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils.timezone import now
from django.db import transaction, IntegrityError

from trader.celery import shared_task
from binance.client import Client

from decimal import Decimal, InvalidOperation
from datetime import datetime


logger = logging.getLogger(__name__)


# Configuración de la API de Binance Testnet
BINANCE_TESTNET_API_KEY = os.getenv('BINANCE_TESTNET_API_KEY')
BINANCE_TESTNET_API_SECRET = os.getenv('BINANCE_TESTNET_API_SECRET')
TESTNET_BASE_URL = os.getenv('TESTNET_BASE_URL')  # URL del Testnet

# Cliente configurado para el entorno de pruebas
client = Client(BINANCE_TESTNET_API_KEY, BINANCE_TESTNET_API_SECRET)
client.API_URL = TESTNET_BASE_URL

