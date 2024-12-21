# dashboard/utils/binance_service.py

import os
from binance.client import Client
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)

# Configuración de la API de Binance Testnet
BINANCE_TESTNET_API_KEY = os.getenv('BINANCE_TESTNET_API_KEY')
BINANCE_TESTNET_API_SECRET = os.getenv('BINANCE_TESTNET_API_SECRET')
TESTNET_BASE_URL = os.getenv('TESTNET_BASE_URL')  # URL del Testnet

# Cliente configurado para el entorno de pruebas
client = Client(BINANCE_TESTNET_API_KEY, BINANCE_TESTNET_API_SECRET)
client.API_URL = TESTNET_BASE_URL


def get_all_tickers():
    """
    Obtiene todos los tickers actuales de Binance.
    
    Retorna:
        List[Dict]: Lista de diccionarios con información de cada ticker.
    """
    try:
        return client.get_ticker()
    except Exception as e:
        logger.error(f"Error al obtener tickers de Binance: {e}")
        return []
