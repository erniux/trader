
import os
import logging
import time
import pytz
import logging

from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils.timezone import now
from django.db import transaction, IntegrityError

from celery import shared_task
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


    """
    Obtiene una lista de símbolos basados en los activos con balance disponible en la cuenta de Binance.

    P

    Retorna:
        List[str]: Lista de símbolos que corresponden a los activos con balance disponible.
    """
    try:
        # Obtener los balances de la cuenta
        account_info = client.get_account()
        balances = account_info['balances']

        # Filtrar balances mayores a 0
        assets_with_balance = [
            balance['asset'] for balance in balances
            if float(balance['free']) > 0 or float(balance['locked']) > 0
        ]
        

        # Filtrar los símbolos que coincidan con los activos con balance
        symbols = Symbol.objects.filter(
            base_asset__in=assets_with_balance
        ).values_list('symbol', flat=True)

        return (account_info)

    except Exception as e:
        print(f"Error al obtener símbolos con balance: {e}")
        return []