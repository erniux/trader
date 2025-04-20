# ws_listener.py

import os
import django
import time
import logging
import redis
import json
from binance import ThreadedWebsocketManager

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trader.settings')
django.setup()

#from dashboard.models import Symbol  

logging.basicConfig(
    level=logging.DEBUG,  # Cambia a DEBUG para más detalles
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)

logger = logging.getLogger(__name__)

BINANCE_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "")

REDIS_HOST =  "redis"
REDIS_PORT =  6379

#WATCHED_SYMBOLS = list(Symbol.objects.values_list('symbol', flat=True))   
#logger.info(WATCHED_SYMBOLS)
WATCHED_SYMBOLS = ["BTCUSDT", "ETHUSDT", "ETHBTC"]

# --- INICIALIZACIÓN DE REDIS ---
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)


def handle_socket_message(msg):
    symbol = msg.get("s")
    last_price = msg.get("c")

    if symbol and last_price:
        logger.warning(f"actualizando precio para {symbol} ::: {last_price}")

        # Guardamos solo el precio en price:{symbol}
        r.set(f"price:{symbol}", last_price)

        # Guardamos el JSON completo del ticker en ticker:{symbol}
        try:
            r.set(f"ticker:{symbol}", json.dumps(msg))
        except Exception as e:
            logger.error(f"[WS] No se pudo guardar el ticker completo para {symbol}: {e}")

        logger.info(f"[WS] Actualizado {symbol} => {last_price}")
    else:
        logger.warning(f"[WS] Mensaje recibido sin datos de precio válidos: {msg}")




def start_websocket():
    """
    Inicia la conexión WebSocket a Binance y se suscribe
    a los streams de ticker para cada símbolo definido en WATCHED_SYMBOLS. y  se van almacenando los precios en redis
    """
    while True:
        try:
            twm = ThreadedWebsocketManager(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET, testnet=True)
            twm.start()

            for sym in WATCHED_SYMBOLS:
                twm.start_symbol_ticker_socket(callback=handle_socket_message, symbol=sym)

            logger.info("WebSocket iniciado. Escuchando precios...")
            twm.join()
        except Exception as e:
            logger.error(f"Error en WebSocket: {e}. Reconectando en 5 segundos...")
            time.sleep(5)

if __name__ == "__main__":
    start_websocket()


