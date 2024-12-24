# ws_listener.py

import os
import time
import logging
import redis
from binance import ThreadedWebsocketManager
from dashboard.models import Symbol

# --- CONFIGURACIÓN DE LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)
logger = logging.getLogger(__name__)

# --- VARIABLES DE ENTORNO ---
BINANCE_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "")

# Asumiendo que en docker-compose.yml el servicio Redis se llama "redis"
REDIS_HOST =  "redis"
REDIS_PORT =  6379

# Lista de símbolos a monitorear

WATCHED_SYMBOLS = Symbol.objects.get('symbol') #["BTCUSDT", "ETHUSDT", "ETHBTC"]

# --- INICIALIZACIÓN DE REDIS ---
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

def handle_socket_message(msg):
    """
    Callback que maneja cada mensaje del stream WebSocket de Binance.
    Esperamos un diccionario con campos como:
    {
      'e': '24hrTicker',
      'E': 123456789,    # Event time
      's': 'BTCUSDT',    # Symbol
      'c': '20000.99',   # Last price (string)
      ...
    }
    """
    symbol = msg.get("s")
    last_price = msg.get("c")

    if symbol and last_price:
        logger.warning(f"actualizando precio para {symbol} ::: {last_price}")
        # Guardamos el precio en Redis con la clave "price:SIMBOLO"
        key = f"price:{symbol}"
        r.set(key, last_price)
        #logger.info(f"[WS] Actualizado {symbol} => {last_price}")
    else:
        logger.warning(f"[WS] Mensaje recibido sin datos de precio válidos: {msg}")

def start_websocket():
    """
    Inicia la conexión WebSocket a Binance y se suscribe
    a los streams de ticker para cada símbolo definido en WATCHED_SYMBOLS.
    """
    twm = ThreadedWebsocketManager(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
    twm.start()

    for sym in WATCHED_SYMBOLS:
        twm.start_symbol_ticker_socket(callback=handle_socket_message, symbol=sym)

    logger.info("WebSocket de Binance iniciado. Escuchando precios...")

    # Mantén el script corriendo
    while True:
        time.sleep(1)

if __name__ == "__main__":
    start_websocket()
