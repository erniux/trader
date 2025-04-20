# dashboard/utils/redis_service.py

import redis
import os
import logging
import json
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

# Configuración de Redis
REDIS_HOST = 'redis'
REDIS_PORT = 6379
REDIS_DB = 0

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def get_price_from_redis(symbol):
    """
    Obtiene el precio de un símbolo específico desde Redis.

    Parámetros:
        symbol (str): Símbolo de la criptomoneda, por ejemplo, 'BTCUSDT'.

    Retorna:
        Decimal: Precio actual o None si no está disponible o hay un error.
    """
    try:
        price = r.get(f"price:{symbol}")
        if price is None:
            logger.warning(f"No hay precio en Redis para {symbol}")
            return None
        return Decimal(price.decode("utf-8"))
    except (InvalidOperation, AttributeError) as e:
        logger.error(f"Error al convertir el precio de {symbol}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error al obtener el precio de Redis para {symbol}: {e}")
        return None


def get_live_price(symbol):
    """
    Obtiene el precio 'c' desde el ticker en Redis.
    Este valor representa el precio de cierre más reciente (last price).
    """
    try:
        key = f"ticker:{symbol}"  # clave donde se guarda el ticker completo
        raw = r.get(key)
        if raw is None:
            logger.warning(f"No hay ticker en Redis para {symbol}")
            return None
        data = json.loads(raw)
        return Decimal(data.get("c")) if "c" in data else None
    except (InvalidOperation, json.JSONDecodeError) as e:
        logger.error(f"Error al leer precio en tiempo real para {symbol}: {e}")
        return None
