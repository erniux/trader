
import os
from celery import shared_task
from binance.client import Client
from .models import HistoricalPrice, ArbitrageOpportunity, Symbol
from .utils.arbitrage import calculate_profit, find_arbitrage_routes, get_price

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
            if price >= Decimal('10000000000') or volume >= Decimal('10000000000'):
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


@shared_task
def check_arbitrage_opportunities():
    """
    Realiza los cálculos de arbitraje triangular con los precios actuales
    y verifica si hay oportunidades de ganancia.
    """
    # Parámetros de trading
    FEE_RATE = Decimal('0.001')  # 0.1 % Comisión
    SLIPPAGE_RATE = Decimal('0.0005')  # 0.05% Deslizamiento de precios

    logger.info(f"Iniciando el cálculo de oportunidades de arbitraje...{time.time()}")

    # Encontrar rutas de arbitraje
    routes = find_arbitrage_routes()
    if routes.empty:
        logger.info("No se encontraron rutas de arbitraje.")
        return

    for _, route in routes.iterrows():
        symbol_1 = route['symbol_1']
        symbol_2 = route['symbol_2']
        symbol_3 = route['symbol_3']
        logger.debug(f"Procesando ruta: {symbol_1} -> {symbol_2} -> {symbol_3}")

        try:
            # Manejo de símbolos invertidos
            if symbol_2.endswith("_INV"):
                symbol_2_base = symbol_2.replace("_INV", "")
                symbol_2_obj = Symbol.objects.filter(symbol=symbol_2_base).first()
                if not symbol_2_obj:
                    logger.warning(f"El símbolo base {symbol_2_base} no existe en la base de datos.")
                    continue
            else:
                symbol_2_obj = Symbol.objects.filter(symbol=symbol_2).first()
                if not symbol_2_obj:
                    logger.warning(f"El símbolo {symbol_2} no existe en la base de datos.")
                    continue

            if symbol_3.endswith("_INV"):
                symbol_3_base = symbol_3.replace("_INV", "")
                symbol_3_obj = Symbol.objects.filter(symbol=symbol_3_base).first()
                if not symbol_3_obj:
                    logger.warning(f"El símbolo base {symbol_3_base} no existe en la base de datos.")
                    continue
            else:
                symbol_3_obj = Symbol.objects.filter(symbol=symbol_3).first()
                if not symbol_3_obj:
                    logger.warning(f"El símbolo {symbol_3} no existe en la base de datos.")
                    continue

            # Obtener los objetos Symbol para los símbolos 1 y 3
            symbol_1_obj = Symbol.objects.filter(symbol=symbol_1).first()
    
            if not symbol_1_obj or not symbol_3_obj:
                logger.warning(f"Uno o más símbolos no existen: {symbol_1}, {symbol_3}")
                continue

            # Obtener los precios de los símbolos
            price_1 = get_price(symbol_1, client)
            price_2 = 1 / get_price(symbol_2_base, client) if symbol_2.endswith("_INV") else get_price(symbol_2, client)
            price_3 = 1 / get_price(symbol_3_base, client) if symbol_3.endswith("_INV") else get_price(symbol_3, client) 

            if not price_1 or not price_2 or not price_3:
                logger.warning(f"Precios no disponibles para la ruta: {symbol_1} -> {symbol_2} -> {symbol_3}")
                continue

            # Calcular ganancia potencial
            profit = calculate_profit(price_1, price_2, price_3, FEE_RATE, SLIPPAGE_RATE)
            logger.debug(f"Profit para la ruta: {profit}")

            if profit > 0:
                logger.info(f"Oportunidad de arbitraje encontrada: {symbol_1} -> {symbol_2} -> {symbol_3}. Ganancia: {profit}")

                # Guardar la oportunidad en la base de datos
                try:
                    with transaction.atomic():
                        opportunity, created = ArbitrageOpportunity.objects.select_for_update().get_or_create(
                            symbol_1=symbol_1_obj,
                            symbol_2=symbol_2_obj,
                            symbol_3=symbol_3_obj,
                            defaults={
                                'route': f"{symbol_1} -> {symbol_2} -> {symbol_3}",
                                'profit': profit
                            }
                        )
                        if not created:
                            # Actualizar el profit si ya existe
                            opportunity.profit = profit
                            opportunity.save()
                except IntegrityError as exc:
                    logger.error(f"Error al guardar la oportunidad: {exc}")
                    continue
            else:
                logger.debug(f"No hay ganancia en la ruta: {symbol_1} -> {symbol_2} -> {symbol_3}::: {profit}")

        except Exception as e:
            logger.warning(f"Error al procesar la ruta {symbol_1} -> {symbol_2} -> {symbol_3}: {e}")
            continue

    logger.info(f"Revisión de todas las oportunidades de arbitraje completada. {time.time()}")


def calculate_profit(price_1, price_2, price_3, fee_rate, slippage_rate):
    """
    Calcula la ganancia potencial de una ruta de arbitraje considerando comisiones y deslizamiento.

    Parámetros:
        price_1 (Decimal): Precio del primer par.
        price_2 (Decimal): Precio del segundo par.
        price_3 (Decimal): Precio del tercer par.
        fee_rate (Decimal): Comisión aplicada en cada operación.
        slippage_rate (Decimal): Deslizamiento estimado en cada operación.

    Retorna:
        Decimal: Ganancia neta estimada, o 0 si no hay ganancia.
    """
    try:
        # Convertir los precios a Decimal
        price_1 = Decimal(price_1)
        price_2 = Decimal(price_2)
        price_3 = Decimal(price_3)

        # Ajustar precios con el deslizamiento
        adjusted_price_1 = price_1 * (1 - slippage_rate)
        adjusted_price_2 = price_2 * (1 - slippage_rate)
        adjusted_price_3 = price_3 * (1 - slippage_rate)

        # Calcular el valor final después de un ciclo de arbitraje
        final_value = adjusted_price_1 * adjusted_price_2 * adjusted_price_3
        
        # Aplicar comisiones
        fee_multiplier = (1 - fee_rate) ** 3
        net_value = final_value * fee_multiplier

        # Retornar ganancia si existe
        return net_value - 1 if net_value > 1 else 0
    except InvalidOperation as e:
        logger.warning(f"Error al calcular el profit: {e}")
        return 0


@shared_task
def check_arbitrage_opportunities_realtime():
    pass
        