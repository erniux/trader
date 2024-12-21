
import os
from celery import shared_task
from binance.client import Client
from .models import MarketPair, HistoricalPrice, ArbitrageOpportunity
from .utils.binance_service import get_all_tickers
from .utils.arbitrage import calculate_profit, find_arbitrage_routes
from .utils.redis_service import get_price_from_redis
from django.db.models import F
from django.utils.timezone import now
from django.db import transaction, IntegrityError
from decimal import Decimal, InvalidOperation
import logging
import redis

logger = logging.getLogger(__name__)

#REDIS_HOST = "localhost"
#REDIS_PORT = 6379
#r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Configuración de la API de Binance Testnet
BINANCE_TESTNET_API_KEY = os.getenv('BINANCE_TESTNET_API_KEY')
BINANCE_TESTNET_API_SECRET = os.getenv('BINANCE_TESTNET_API_SECRET')
TESTNET_BASE_URL = os.getenv('TESTNET_BASE_URL')  # URL del Testnet

# Cliente configurado para el entorno de pruebas
client = Client(BINANCE_TESTNET_API_KEY, BINANCE_TESTNET_API_SECRET)
client.API_URL = TESTNET_BASE_URL


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

            # Verifica si el par existe en la base de datos
            base_currency, quote_currency = symbol[:-3], symbol[-3:]  # Ejemplo: BTCUSDT -> BTC, USDT
            #print(base_currency, quote_currency)
            pair, created = MarketPair.objects.get_or_create(
                base_currency=base_currency,
                quote_currency=quote_currency,
                exchange='Binance'
            )

            # Guardamos el precio histórico

            HistoricalPrice.objects.create(
                market_pair=pair,
                price=price,
                volume=volume,
                timestamp=now()
            )

        except Exception as e:
            # Que mande error pero que continue con los demas tickers
            logger.warning(f"Error al consultar precios de Binance: {e},  {ticker}, {InvalidOperation}")
            continue


@shared_task
def check_arbitrage_opportunities(): 
    """
    Realiza los cálculos de arbitraje triangular con los precios históricos
    y verifica si hay oportunidades de ganancia.
    """
    #Parametros de trading
    FEE_RATE = Decimal(0.01)   #0.1 % De Comision
    SLIPPAGE_RATE = Decimal('0.0005') #=.05% de deslizamiento de precios
    
    logger.info("Iniciando el cálculo de oportunidades de arbitraje...")
    
    try:    
        market_pairs = MarketPair.objects.filter(exchange='Binance')

        #Encontrar todos los MarketPair disponibles
        routes = find_arbitrage_routes(market_pairs)
        logger.debug(f"Profit calculado para la ruta ::: {pair1}->{pair2}->{pair3}:: {profit}")

        # Iterar sobre todos los posibles ciclos de tres pares
        for route in routes:
            pair1, pair2, pair3 = route
            try:
                price1 = HistoricalPrice.objects.filter(market_pairs=pair1).latest('detected_at').price
                price2 = HistoricalPrice.objects.filter(market_pair=pair2).latest('detected_at').price
                price3 = HistoricalPrice.objects.filter(market_pair=pair3).latest('detected_at').price
                
                # Calcular la ganancia potencial
                profit = calculate_profit(price1, price2, price3, Decimal('0.01'), Decimal('0.0005'))
                logger.debug(f"Profit calculado para la ruta {pair1} -> {pair2} -> {pair3}: {profit}")
                
            except (HistoricalPrice.DoesNotExist, InvalidOperation) as e:
                logger.warning(f"datos de precio no disponible o invalidos para {pair1}->{pair2}->{pair3}::: {e}")
                continue
        
            if profit > 0:
                logger.info(
                    f"Oportunidad de arbitraje encontrada: {pair1.base_currency} -> "
                    f"{pair2.base_currency} -> {pair3.base_currency}. Ganancia: {profit}"
                )

                # Guardar la oportunidad
                try:
                    with transaction.atomic():
                        # Intentar obtener el objeto con un lock
                        opportunity, created = ArbitrageOpportunity.objects.select_for_update().get_or_create(
                            pair_1=pair1,
                            pair_2=pair2,
                            pair_3=pair3,
                            defaults={'profit': profit}
                        )
                        if not created:
                            # Actualizar el profit si ya existe
                            opportunity.profit = profit
                            opportunity.save()
                    logger.info(
                        f"Oportunidad de arbitraje encontrada: {pair1.base_currency} -> "
                        f"{pair2.base_currency} -> {pair3.base_currency}. Ganancia: {profit}"
                    )
                except IntegrityError as exc:
                    logger.error(f"IntegrityError al guardar la oportunidad de arbitraje para {pair1}-{pair2}-{pair3}: {exc}")
                    # Calcular el backoff exponencial
                    #countdown = 2 ** self.request.retries
                    #logger.info(f"Reintentando en {countdown} segundos...")
                    #raise self.retry(exc=exc, countdown=countdown)

            else:
                logger.debug(
                    f"No hay ganancia en el ciclo: {pair1.base_currency} -> "
                    f"{pair2.base_currency} -> {pair3.base_currency}."
                )

        logger.info("Revisión de todas las oportunidades de arbitraje completada.")

    except Exception as e:
        logger.error(f"Error al revisar todas las oportunidades de arbitraje: {e}")
        #raise self.retry(exc=e, countdown=60)  # Reintentar en 1 minuto


@shared_task
def check_arbitrage_opportunities_realtime():
    
    #Revisa precios en Redis y calcula si hay arbitraje
    #con BTC, ETH, USDT, etc. (ejemplo básico)
    
    #r = redis.Redis(host="redis", port="6379", db=0)

    # Definamos un triángulo simple
    symbols = ["BTCUSDT", "ETHUSDT", "ETHBTC"]

    # Parámetros de trading (ajusta según tu estrategia)
    FEE_RATE = Decimal('0.001')        # 0.1% de comisión
    SLIPPAGE_RATE = Decimal('0.0005')  # 0.05% de slippage (ejemplo)

    try:
        # Obtener los precios desde Redis
        prices = {}
        for sym in symbols:
            #price = r.get(f"price:{sym}")
            price = get_price_from_redis(sym)
            if price is None:
                logger.warning(f"No hay precio en Redis para {sym}")
                return  # Salir de la tarea si falta algún precio
            prices[sym] = price
            logger.debug(f"Precio obtenido de Redis - {sym}::: {price}")

        # Asignar los precios a variables para claridad
        btc_usdt = prices["BTCUSDT"]  # USDT por 1 BTC
        eth_usdt = prices["ETHUSDT"]  # USDT por 1 ETH
        eth_btc = prices["ETHBTC"]    # BTC por 1 ETH

        # Iniciar el cálculo de arbitraje con 1 BTC
        profit = calculate_profit(btc_usdt, eth_usdt, eth_btc, FEE_RATE, SLIPPAGE_RATE)

        if profit > 0:
            # Describir la ruta de arbitraje
            route = "BTCUSDT -> ETHUSDT -> ETHBTC -> BTCUSDT"

            # Registrar la oportunidad de arbitraje
            try:
                pair1 = MarketPair.objects.get(base_currency="BTC", quote_currency="USDT", exchange='Binance')
                pair2 = MarketPair.objects.get(base_currency="ETH", quote_currency="USDT", exchange='Binance')
                pair3 = MarketPair.objects.get(base_currency="ETH", quote_currency="BTC", exchange='Binance')
            except MarketPair.DoesNotExist as e:
                logger.error(f"No se encontraron los MarketPairs necesarios para el arbitraje: {e}")
                return
            
            # Registrar la oportunidad de arbitraje usando `update_or_create`
            try:
                with transaction.atomic():
                    # Intentar obtener el objeto con un lock
                    opportunity, created = ArbitrageOpportunity.objects.select_for_update().get_or_create(
                        pair_1=pair1,
                        pair_2=pair2,
                        pair_3=pair3,
                        defaults={'profit': profit}
                    )
                    if not created:
                        # Actualizar el profit si ya existe
                        opportunity.profit = profit
                        opportunity.save()
                logger.info(
                    f"Oportunidad de arbitraje encontrada: {pair1.base_currency} -> "
                    f"{pair2.base_currency} -> {pair3.base_currency}. Ganancia: {profit}"
                )
            except IntegrityError as exc:
                logger.error(f"IntegrityError al guardar la oportunidad de arbitraje para {pair1}-{pair2}-{pair3}: {exc}")
                # Calcular el backoff exponencial
                #countdown = 2 ** self.request.retries
                #logger.info(f"Reintentando en {countdown} segundos...")
                #raise self.retry(exc=exc, countdown=countdown)


            if created:
                logger.info(f"Oportunidad de arbitraje encontrada: {route} - Ganancia: {profit:.8f} BTC")
            else:
                logger.debug(f"Oportunidad de arbitraje ya registrada: {route} - Ganancia: {profit:.8f} BTC")
        else:
            logger.debug("No hay oportunidad de arbitraje en este ciclo.")

    except Exception as e:
        logger.error(f"Error al revisar todas las oportunidades de arbitraje: {e}")
        #raise self.retry(exc=e, countdown=60)  # Reintentar en 1 minuto
        