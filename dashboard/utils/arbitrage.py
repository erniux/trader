# dashboard/utils/arbitrage.py

from decimal import Decimal
from collections import defaultdict
import logging
import pandas as pd
from dashboard.models import Symbol, HistoricalPrice
import redis
from binance.client import Client
from .redis_service import get_price_from_redis

redis_client = redis.StrictRedis(host='redis', port=6379, db=0)

logger = logging.getLogger(__name__)


def calculate_profit(price_a, price_b, price_c, fee_rate=Decimal('0.01'), slippage_rate=Decimal('0.0005')):
    """
    Calcula la ganancia potencial de arbitraje triangular.

    Parámetros:
        price_a (Decimal): Precio del par 1 (base_currency/quote_currency).
        price_b (Decimal): Precio del par 2.
        price_c (Decimal): Precio del par 3.
        fee_rate (Decimal): Tasa de comisión.
        slippage_rate (Decimal): Tasa de deslizamiento.

    Retorna:
        Decimal: Ganancia potencial.
    """
    initial_amount = Decimal('1')  # Suponemos que comenzamos con 1 unidad de la primera moneda

    try:
        # Paso 1: Convertir pair1.base -> pair1.quote
        step1 = initial_amount * price_a
        step1_after_fee = step1 * (Decimal('1') - fee_rate)
        step1_final = step1_after_fee * (Decimal('1') - slippage_rate)

        # Paso 2: Convertir pair2.base -> pair2.quote
        step2 = step1_final / price_b
        step2_after_fee = step2 * (Decimal('1') - fee_rate)
        step2_final = step2_after_fee * (Decimal('1') - slippage_rate)

        # Paso 3: Convertir pair3.base -> pair3.quote (final)
        step3 = step2_final * price_c
        step3_after_fee = step3 * (Decimal('1') - fee_rate)
        final_amount = step3_after_fee * (Decimal('1') - slippage_rate)

        # Calcular la ganancia
        profit = final_amount - step1
        if (profit > 0 and profit > step1):
            logger.warning(f"---> PROFIT SEGUN YO!!!!!! ---> {profit-step1}")


        return profit

    except Exception as e:
        logger.error(f"Error al calcular la ganancia de arbitraje: {e}")
        return Decimal('0')


def find_arbitrage_routes():
    """
    Encuentra triángulos de arbitraje utilizando los datos reales de Symbol.

    Retorna:
        List[Dict]: Lista de rutas de arbitraje (triángulos) válidas.
    """
    try:
        # Cargar todos los símbolos de la base de datos
        symbols_queryset = Symbol.objects.all().values('symbol', 'base_asset', 'quote_asset')
        symbols_df = pd.DataFrame(list(symbols_queryset))

        
        # Crear pares invertidos y agregarlos al DataFrame
        inverted_pairs = symbols_df.copy()
        inverted_pairs['symbol'] = inverted_pairs['symbol'] + '_INV'
        inverted_pairs = inverted_pairs.rename(
            columns={'base_asset': 'quote_asset', 'quote_asset': 'base_asset'}
        )
        augmented_df = pd.concat([symbols_df, inverted_pairs])

        # Paso 1: Crear conexiones symbol1 -> symbol2
        step1 = augmented_df.merge(
            augmented_df,
            left_on='quote_asset',
            right_on='base_asset',
            suffixes=('_1', '_2')
        )


        # Paso 2: Renombrar columnas del DataFrame original antes del merge
        symbols_renamed = augmented_df.rename(
            columns={
                'symbol': 'symbol_3',
                'base_asset': 'base_asset_3',
                'quote_asset': 'quote_asset_3'
            }
        )

        # Crear conexiones symbol2 -> symbol3 que cierren el triángulo
        step2 = step1.merge(
            symbols_renamed,
            left_on='quote_asset_2',
            right_on='base_asset_3'
        )

        # Validar si el DataFrame tiene datos antes de continuar
        if step2.empty:
            print("No se encontraron triángulos en los datos proporcionados.")
            return pd.DataFrame()

        # Paso 3: Filtrar triángulos válidos
        valid_triangles = step2[
            step2['quote_asset_3'] == step2['base_asset_1']  # Cierra el triángulo
        ]

        # Paso 4: Seleccionar columnas relevantes
        routes = valid_triangles[[
            'symbol_1', 'symbol_2', 'symbol_3',  # Nombres de los símbolos
            'base_asset_1', 'quote_asset_1',     # Primera conexión
            'quote_asset_2',                     # Segunda conexión
            'quote_asset_3'                      # Tercera conexión
        ]]

        return routes.reset_index(drop=True)

    except Exception as e:
        logger.error(f"Error al encontrar rutas de arbitraje: {e}")
        return pd.DataFrame()
    

def get_price(symbol, binance_client):
    """
    Obtiene el precio de un símbolo desde Redis o la API de Binance,
    manejando símbolos invertidos (_INV).

    Parámetros:
        symbol (str): El símbolo para el cual obtener el precio.
        binance_client (Client): Cliente de Binance para obtener datos en tiempo real.

    Retorna:
        float: El precio más reciente, o None si no existe.
    """
    # Verificar si el símbolo está invertido
    is_inverted = symbol.endswith("_INV")
    base_symbol = symbol.replace("_INV", "") if is_inverted else symbol

    # 1. Intentar obtener el precio desde Redis
    try:
        key = f"price:{base_symbol}"  # Clave en Redis
        price = redis_client.get(key)
        if price:
            price = float(price)
            # Si el símbolo es invertido, calcular el inverso
            return 1 / price if is_inverted else price
    except Exception as e:
        logger.error(f"Error al obtener el precio de {base_symbol} desde Redis: {e}")

    # 2. Obtener el precio desde Binance si no está en Redis
    try:
        ticker = binance_client.get_symbol_ticker(symbol=base_symbol)
        price = float(ticker['price'])
        # Si el símbolo es invertido, calcular el inverso
        return 1 / price if is_inverted else price
    except Exception as e:
        logger.error(f"Error al obtener el precio de {base_symbol} desde Binance: {e}")
        return None