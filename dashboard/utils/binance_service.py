from binance import Client
import os

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

client = Client(api_key, api_secret, tld="com", testnet=False)

def fetch_last_candles(symbol: str, interval: str = "1m", limit: int = 1000):
    """
    Devuelve lista de (close, close_time) en UTC para los últimos `limit` candles.
    """
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    result = []
    for k in klines:
        close_price = float(k[4])
        close_time = int(k[6]) / 1000  # ms → s
        result.append((close_price, close_time))
    return result
