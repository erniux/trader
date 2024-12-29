
import os
from celery import shared_task
from binance.client import Client
from .models import HistoricalPrice, ArbitrageOpportunity, Symbol
from .utils.arbitrage import calculate_profit, find_arbitrage_routes, get_price, handle_arbitrage_opportunity, get_balance
from django.db.models import F
from django.utils.timezone import now
from django.db import transaction, IntegrityError
from decimal import Decimal, InvalidOperation
from datetime import datetime
import logging
import time
import pytz



logger = logging.getLogger(__name__)


# Configuración de la API de Binance Testnet
BINANCE_TESTNET_API_KEY = os.getenv('BINANCE_TESTNET_API_KEY')
BINANCE_TESTNET_API_SECRET = os.getenv('BINANCE_TESTNET_API_SECRET')
TESTNET_BASE_URL = os.getenv('TESTNET_BASE_URL')  # URL del Testnet

# Cliente configurado para el entorno de pruebas
client = Client(BINANCE_TESTNET_API_KEY, BINANCE_TESTNET_API_SECRET)
client.API_URL = TESTNET_BASE_URL

FEE_RATE = Decimal('0.001')  # 0.1 % Comisión
SLIPPAGE_RATE = Decimal('0.0005')  # 0.05% Deslizamiento de precios


@shared_task
def fetch_and_save_symbols_with_time():
    """
    Obtiene información de símbolos desde Binance, incluye el tiempo del servidor,
    y guarda los datos en la base de datos tabla Symbol
    """
    try:
        # Obtener datos de exchange info
        exchange_info = client.get_exchange_info()
        server_time = client.get_server_time()['serverTime']

        # Convertir server_time a datetime con zona horaria
        utc_tz = pytz.UTC  # Zona horaria UTC
        server_datetime = datetime.fromtimestamp(server_time / 1000, tz=utc_tz)

        # Procesar símbolos con tiempo del servidor
        symbols_data = [
            {
                'symbol': symbol['symbol'],
                'baseAsset': symbol['baseAsset'],
                'quoteAsset': symbol['quoteAsset'],
                'server_time': server_datetime
            }
            for symbol in exchange_info['symbols']
        ]

        # Guardar en PostgreSQL usando Django ORM
        for data in symbols_data:
            Symbol.objects.update_or_create(
                symbol=data['symbol'],
                defaults={
                    'base_asset': data['baseAsset'],
                    'quote_asset': data['quoteAsset'],
                    'server_time': data['server_time']
                }
            )

        logger.info(f"Se actualizaron {len(symbols_data)} símbolos en la base de datos con server_time {server_datetime}.")

    except Exception as e:
        logger.error(f"Error al obtener y guardar símbolos: {e}")
        raise e


@shared_task
def fetch_binance_prices():
    """
    Consulta los precios actuales de Binance y guarda los datos en la base de datos.  
    Obtenemos todos los precios actuales
    """
    tickers = client.get_ticker()

    for ticker in tickers:
        try:
            symbol = ticker['symbol']
            price = Decimal(ticker['lastPrice'])
            volume = Decimal(ticker['volume'])
            
            # Buscar el símbolo correspondiente en la tabla Symbol
            symbol_id = Symbol.objects.get(symbol=symbol)

            # Validar si el precio o volumen son demasiado grandes
            if price >= Decimal('100000000000.0000000000') or volume >= Decimal('100000000000.0000000000'):
                logger.warning(f"Valor fuera de rango: SYMBOL={symbol}, PRICE={price}, VOLUME={volume}")
                continue

            # Guardar el precio histórico
            HistoricalPrice.objects.update_or_create(
                symbol=symbol_id,
                timestamp=now(),
                defaults={
                    'price': price,
                    'volume': volume
                }
            )

        except Symbol.DoesNotExist:
            logger.warning(f"El símbolo {symbol} no existe en la base de datos.")
            continue
        except Decimal.InvalidOperation:
            logger.warning(f"Error al convertir precios o volumen para {symbol}: {ticker}")
            continue
        except Exception as e:
            logger.warning(f"Error al consultar precios de Binance: {e}, {ticker}")
            continue


from decimal import Decimal
import time

from celery import shared_task
from django.db import transaction, IntegrityError

# Supón que estos son tus helpers y modelos:
# from .models import Symbol, ArbitrageOpportunity
# from .utils import find_arbitrage_routes, get_price, get_balance, calculate_profit, FEE_RATE, SLIPPAGE_RATE

import logging

logger = logging.getLogger(__name__)

def get_symbol_and_price(symbol: str, client) -> tuple | None:
    """
    Dada una cadena de símbolo (ej. "BTCUSDT" o "BTCUSDT_INV"), 
    retorna una tupla (obj_symbol, price) o None si algo falla.
    """
    base_symbol = symbol.replace("_INV", "")
    symbol_obj = Symbol.objects.filter(symbol=base_symbol).first()
    if not symbol_obj:
        logger.warning(f"Símbolo no encontrado en BD: {symbol}")
        return None
    
    try:
        price = get_price(base_symbol, client)
        if not price:
            logger.warning(f"Precio no disponible para el símbolo: {symbol}")
            return None
        # Si es símbolo invertido, el precio es el inverso
        if symbol.endswith("_INV"):
            price = 1 / price
    except Exception as e:
        logger.warning(f"Error al obtener precio para {symbol}: {e}")
        return None
    
    return (symbol_obj, price)


@shared_task
def check_arbitrage_opportunities(min_notional=Decimal("10.0")):
    """
    Realiza los cálculos de arbitraje triangular con los precios actuales,
    verifica si hay oportunidades de ganancia y filtra según el monto mínimo requerido para operar.

    Parámetros:
        min_notional (Decimal): Monto mínimo requerido para operar en SPOT.
    """
    logger.info(f"Iniciando el cálculo de oportunidades de arbitraje... {time.time()}")

    # Encontrar rutas de arbitraje
    routes = find_arbitrage_routes()
    if routes.empty:
        logger.info("No se encontraron rutas de arbitraje.")
        return

    for _, route in routes.iterrows():
        symbol_1_name = route['symbol_1']
        symbol_2_name = route['symbol_2']
        symbol_3_name = route['symbol_3']

        logger.debug(f"Procesando ruta: {symbol_1_name} -> {symbol_2_name} -> {symbol_3_name}")

        try:
            # Obtener objeto y precio de cada símbolo
            data_1 = get_symbol_and_price(symbol_1_name, client)
            data_2 = get_symbol_and_price(symbol_2_name, client)
            data_3 = get_symbol_and_price(symbol_3_name, client)

            # Si alguno es None, se descarta la ruta
            if not all([data_1, data_2, data_3]):
                logger.warning(
                    f"Uno o más símbolos no existen o no tienen precio: "
                    f"{symbol_1_name}, {symbol_2_name}, {symbol_3_name}"
                )
                continue

            symbol_1_obj, price_1 = data_1
            symbol_2_obj, price_2 = data_2
            symbol_3_obj, price_3 = data_3

            # Calcular ganancia potencial
            profit = calculate_profit(price_1, price_2, price_3, FEE_RATE, SLIPPAGE_RATE)
            logger.debug(f"Profit estimado para la ruta: {profit}")

            # Si no hay ganancia, se omite
            if profit <= 0:
                logger.debug(f"No hay ganancia en la ruta: {symbol_1_name} -> {symbol_2_name} -> {symbol_3_name}")
                continue

            # Verificar balance disponible y monto mínimo requerido
            asset = symbol_1_name[:3]  # Ajusta esta lógica según tu convención de símbolos
            balance = get_balance(client, asset)
            notional_value = balance * Decimal(price_1)

            if notional_value < min_notional:
                logger.warning(
                    f"Oportunidad descartada por no cumplir con el monto mínimo requerido: "
                    f"{notional_value} < {min_notional}"
                )
                continue

            logger.info(f"Oportunidad detectada con el asset {asset} en la ruta {route}")

            # Guardar la oportunidad en la base de datos
            try:
                with transaction.atomic():
                    opportunity, created = (
                        ArbitrageOpportunity.objects
                        .select_for_update()
                        .get_or_create(
                            symbol_1=symbol_1_obj,
                            symbol_2=symbol_2_obj,
                            symbol_3=symbol_3_obj,
                            defaults={
                                'route': f"{symbol_1_name} -> {symbol_2_name} -> {symbol_3_name}",
                                'profit': profit
                            }
                        )
                    )
                    if not created:
                        # Actualizar el profit si la oportunidad ya existe
                        opportunity.profit = profit
                        opportunity.save()

            except IntegrityError as exc:
                logger.error(f"Error al guardar la oportunidad: {exc}")
                continue

        except Exception as e:
            logger.warning(
                f"Error inesperado al procesar la ruta "
                f"{symbol_1_name} -> {symbol_2_name} -> {symbol_3_name}: {e}"
            )
            continue

    logger.info(f"Revisión de oportunidades de arbitraje completada. {time.time()}")



@shared_task
def process_arbitrage_opportunities():
    """
    Procesa oportunidades de arbitraje y ejecuta operaciones.
    """
    profitable_opportunities = ArbitrageOpportunity.objects.filter(profit__gt=0)

    if not profitable_opportunities.exists():
        logger.info("No hay oportunidades rentables disponibles.")
        return

    for opportunity in profitable_opportunities:
        success = handle_arbitrage_opportunity(opportunity, client)
        if success:
            logger.info(f"Oportunidad procesada con éxito: {opportunity.route}")
        else:
            logger.warning(f"Fallo al procesar la oportunidad: {opportunity.route}")


@shared_task
def get_symbols_with_balance():
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

        return list(assets_with_balance)

    except Exception as e:
        print(f"Error al obtener símbolos con balance: {e}")
        return []