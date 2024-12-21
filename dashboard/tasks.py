import os
from celery import shared_task
from binance.client import Client
from .models import MarketPair, HistoricalPrice, ArbitrageOpportunity
from django.db.models import F
from django.utils.timezone import now
from decimal import Decimal, InvalidOperation
import logging
import redis

logger = logging.getLogger(__name__)

REDIS_HOST = "localhost"
REDIS_PORT = 6379
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

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
    """
    
    # Obtenemos todos los precios actuales
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
        market_pairs = MarketPair.objects.all()

        # Iterar sobre todos los posibles ciclos de tres pares
        for pair1 in market_pairs:
            for pair2 in market_pairs:
                for pair3 in market_pairs:
                    # Asegurarnos de que los pares son diferentes
                    if pair1 == pair2 or pair2 == pair3 or pair1 == pair3:
                        continue
                    
                    # Comprobamos si el ciclo de arbitraje es válido
                    # Validar que los pares encajan en un ciclo:
                    # (1) pair1.quote == pair2.base
                    # (2) pair2.quote == pair3.base
                    # (3) pair3.quote == pair1.base
                    # Esto significa: base1 -> quote1 -> base2 -> quote2 -> base3 -> quote3 -> base1
                    
                    if pair1.quote_currency == pair2.base_currency and pair2.quote_currency == pair3.base_currency and pair3.quote_currency == pair1.base_currency:
                        # Obtener los últimos precios históricos de cada par
                        try:
                            price1 = HistoricalPrice.objects.filter(market_pair=pair1).latest('timestamp').price
                            price2 = HistoricalPrice.objects.filter(market_pair=pair2).latest('timestamp').price
                            price3 = HistoricalPrice.objects.filter(market_pair=pair3).latest('timestamp').price

                            # Convertir los precios a Decimal
                            price1 = Decimal(price1)
                            price2 = Decimal(price2)
                            price3 = Decimal(price3)
                        
                        except (HistoricalPrice.DoesNotExist, InvalidOperation) as exc:
                            logger.warning(f"Datos de precio no disponibles o inválidos: {exc}")
                            continue
                        

                        # Realizamos los cálculos de arbitraje
                        initial_amount = Decimal(1)  # Suponemos que comenzamos con 1 unidad de la primera moneda
                        
                        # Paso 1: Convertir pair1.base -> pair1.quote
                        # Ej: 1 BTC * (20000 USDT/BTC) => 20000 USDT
                        # Aplica fees y slippage
                        step1 = initial_amount * price1
                        step1_after_fee = step1 * (Decimal('1') - FEE_RATE)
                        step1_final = step1_after_fee * (Decimal('1') - SLIPPAGE_RATE)
                        
                        # Paso 2: Convertir pair2.base -> pair2.quote
                        # Ej: 20000 USDT * (0.001 ETH/USDT) => 20 ETH (hipotético)
                        step2 = step1_final * price2
                        step2_after_fee = step2 * (Decimal('1') - FEE_RATE)
                        step2_final = step2_after_fee * (Decimal('1') - SLIPPAGE_RATE)
                        
                        # Paso 3: Convertir pair3.base -> pair3.quote (final)
                        # Ej: 20 ETH * (0.07 BTC/ETH) => 1.4 BTC
                        step3 = step2_final * price3
                        step3_after_fee = step3 * (Decimal('1') - FEE_RATE)
                        final_amount = step3_after_fee * (Decimal('1') - SLIPPAGE_RATE)

                        # Verificar si hemos ganado más de 1 unidad en el ciclo de arbitraje
                        profit = final_amount - initial_amount

                        # Si es mayor que 0, hay oportunidad
                        if profit > 0:
                            logger.info(
                                f"Oportunidad de arbitraje encontrada: {pair1.base_currency} -> "
                                f"{pair2.base_currency} -> {pair3.base_currency}. Ganancia: {profit}"
                            )

                            # Guarda la oportunidad
                            ArbitrageOpportunity.objects.get_or_create(
                                pair_1=pair1,
                                pair_2=pair2,
                                pair_3=pair3,
                                defaults={'profit': profit}
                            )
                        else:
                            logger.debug(
                                f"No hay ganancia en el ciclo: {pair1.base_currency} -> "
                                f"{pair2.base_currency} -> {pair3.base_currency}."
                            )
        
        print("Cálculo de arbitraje completado.")
                    
    except Exception as e:
        print(f"Error al calcular oportunidades de arbitraje: {e}")


@shared_task
def check_arbitrage_opportunities_realtime():
    """
    Revisa precios en Redis y calcula si hay arbitraje
    con BTC, ETH, USDT, etc. (ejemplo básico)
    """
    r = redis.Redis(host="redis", port="6379", db=0)

    # Definamos un triángulo simple
    symbols = ["BTCUSDT", "ETHUSDT", "ETHBTC"]

    # Parámetros de trading (ajusta según tu estrategia)
    FEE_RATE = Decimal('0.001')        # 0.1% de comisión
    SLIPPAGE_RATE = Decimal('0.0005')  # 0.05% de slippage (ejemplo)

    try:
        # Obtener los precios desde Redis
        prices = {}
        for sym in symbols:
            price = r.get(f"price:{sym}")
            if price is None:
                logger.warning(f"No hay precio en Redis para {sym}")
                return  # Salir de la tarea si falta algún precio
            try:
                prices[sym] = Decimal(price.decode("utf-8"))
            except (InvalidOperation, AttributeError) as e:
                logger.error(f"Error al convertir el precio de {sym}: {e}")
                return  # Salir de la tarea si hay un error de conversión

        # Asignar los precios a variables para claridad
        btc_usdt = prices["BTCUSDT"]  # USDT por 1 BTC
        eth_usdt = prices["ETHUSDT"]  # USDT por 1 ETH
        eth_btc = prices["ETHBTC"]    # BTC por 1 ETH

        # Iniciar el cálculo de arbitraje con 1 BTC
        initial_amount = Decimal('1')

        # Paso 1: BTC -> USDT
        step1 = initial_amount * btc_usdt
        step1_after_fee = step1 * (Decimal('1') - FEE_RATE)
        step1_final = step1_after_fee * (Decimal('1') - SLIPPAGE_RATE)

        # Paso 2: USDT -> ETH
        step2 = step1_final / eth_usdt
        step2_after_fee = step2 * (Decimal('1') - FEE_RATE)
        step2_final = step2_after_fee * (Decimal('1') - SLIPPAGE_RATE)

        # Paso 3: ETH -> BTC
        step3 = step2_final * eth_btc
        step3_after_fee = step3 * (Decimal('1') - FEE_RATE)
        final_amount = step3_after_fee * (Decimal('1') - SLIPPAGE_RATE)

        # Calcular la ganancia
        profit = final_amount - initial_amount

        if profit > 0:
            # Describir la ruta de arbitraje
            route = "BTCUSDT -> ETHUSDT -> ETHBTC -> BTCUSDT"

            # Registrar la oportunidad de arbitraje
            opportunity, created = ArbitrageOpportunity.objects.get_or_create(
                pair_1=MarketPair.objects.get(base_currency="BTC", quote_currency="USDT", exchange='Binance'),
                pair_2=MarketPair.objects.get(base_currency="ETH", quote_currency="USDT", exchange='Binance'),
                pair_3=MarketPair.objects.get(base_currency="ETH", quote_currency="BTC", exchange='Binance'),
                defaults={'profit': profit}
            )

            if created:
                logger.info(f"Oportunidad de arbitraje encontrada: {route} - Ganancia: {profit:.8f} BTC")
            else:
                logger.debug(f"Oportunidad de arbitraje ya registrada: {route} - Ganancia: {profit:.8f} BTC")
        else:
            logger.debug("No hay oportunidad de arbitraje en este ciclo.")

    except Exception as e:
        logger.error(f"Error al calcular oportunidades de arbitraje: {e}")