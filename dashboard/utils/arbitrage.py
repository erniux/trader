# dashboard/utils/arbitrage.py

from decimal import Decimal
from collections import defaultdict
import logging
import pandas as pd
from dashboard.models import Symbol, HistoricalPrice, TransactionLog
import redis
from binance.client import Client
from .redis_service import get_price_from_redis
import time
from decimal import Decimal, ROUND_DOWN

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
            logger.error(f"No se encontraron triángulos en los datos proporcionados.")
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
    


def execute_order(binance_client, symbol, side, quantity, price=None):
    """
    Ejecuta una orden en Binance.

    Parámetros:
        binance_client (Client): Cliente de Binance.
        symbol (str): El símbolo del par (e.g., 'BTCUSDT').
        side (str): 'BUY' o 'SELL'.
        quantity (Decimal): Cantidad a operar.
        price (Decimal, optional): Precio límite. Si no se proporciona, es una orden de mercado.

    Retorna:
        dict: Respuesta de Binance para la orden o None si falla.
    """
    try:
        # Obtener información del símbolo y restricciones de cantidad
        symbol_info = binance_client.get_symbol_info(symbol)
        lot_size_filter = next(
            (f for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE"),
            None
        )

        if not lot_size_filter:
            raise ValueError(f"No se encontró el filtro LOT_SIZE para el símbolo {symbol}")

        min_qty = Decimal(lot_size_filter["minQty"])
        max_qty = Decimal(lot_size_filter["maxQty"])
        step_size = Decimal(lot_size_filter["stepSize"])

        # Determinar el balance disponible
        asset = symbol[:3] if side == "SELL" else symbol[3:]
        balance = get_balance(binance_client, asset)

        if side == "BUY" and price:
            required_balance = quantity * Decimal(price)
        else:
            required_balance = quantity

        if required_balance > balance:
            raise ValueError(
                f"Balance insuficiente para {side} {symbol}. "
                f"Balance disponible: {balance}, Requerido: {required_balance}"
            )

        # Ajustar la cantidad al múltiplo más cercano de stepSize
        adjusted_quantity = (quantity // step_size) * step_size

        if adjusted_quantity < min_qty or adjusted_quantity > max_qty:
            raise ValueError(
                f"La cantidad ajustada {adjusted_quantity} no está dentro del rango permitido: "
                f"{min_qty} - {max_qty}"
            )

        # Crear la orden
        if price:
            formatted_price = "{:.8f}".format(price).rstrip('0').rstrip('.')
            order = binance_client.create_order(
                symbol=symbol,
                side=side,
                type="LIMIT",
                timeInForce="GTC",
                quantity=float(adjusted_quantity),
                price=formatted_price
            )
        else:
            order = binance_client.create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=float(adjusted_quantity)
            )

        return order

    except Exception as e:
        logger.error(f"Error al ejecutar la orden {side} para {symbol}: {e}")
        return None



def simulate_trade(opportunity, side, quantity, price=None):
    """
    Simula una operación de compra o venta.

    Parámetros:
        opportunity (ArbitrageOpportunity): Instancia de la oportunidad de arbitraje asociada.
        side (str): 'BUY' o 'SELL'.
        quantity (Decimal): Cantidad a comprar/vender.
        price (Decimal, optional): Precio límite.

    Retorna:
        dict: Detalles de la operación simulada.
    """
    symbol = opportunity.symbol_1.symbol if side == "BUY" else opportunity.symbol_2.symbol
    logger.info(f"Simulación de {side} para {symbol}: Cantidad={quantity}, Precio={price}")
    return {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "status": "SIMULATED"
    }

def calculate_quantity(opportunity, price, binance_client):
    """
    Calcula la cantidad a operar basada en un capital fijo.

    Parámetros:
        opportunity (ArbitrageOpportunity): Instancia de la oportunidad.
        price (Decimal): Precio actual del símbolo.

    Retorna:
        Decimal: Cantidad calculada.

        capital_usdt = Decimal("100")  # Capital fijo en USDT
    return capital_usdt / price
    """

    account_info = binance_client.get_account()
    for balance in account_info["balances"]:
        print(balance)


    


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


from datetime import datetime

def handle_arbitrage_opportunity(opportunity, binance_client):
    """
    Procesa una oportunidad de arbitraje específica.

    Parámetros:
        opportunity (ArbitrageOpportunity): La oportunidad de arbitraje a procesar.
        binance_client (Client): Cliente de Binance para ejecutar órdenes.

    Retorna:
        bool: True si la operación fue exitosa, False en caso contrario.
    """
    try:
        # Extraer símbolos desde la ruta de la oportunidad
        symbols = opportunity.route.split(" -> ")
        symbol_1_name = symbols[0]
        symbol_2_name = symbols[1]
        symbol_3_name = symbols[2]

        logger.info(f"Procesando oportunidad: {opportunity.route}")

        # Obtener precios
        price_1 = Decimal(get_price(symbol_1_name, binance_client))
        price_2 = Decimal(get_price(symbol_2_name.replace("_INV", ""), binance_client)) if "_INV" in symbol_2_name else Decimal(get_price(symbol_2_name, binance_client))
        price_3 = Decimal(get_price(symbol_3_name.replace("_INV", ""), binance_client)) if "_INV" in symbol_3_name else Decimal(get_price(symbol_3_name, binance_client))

        if not price_1 or not price_2 or not price_3:
            logger.warning(f"Precios no disponibles para la oportunidad: {opportunity.route}")
            return False

        # Determinar el activo base para el balance (del primer símbolo)
        asset = symbol_1_name[:3] if "BUY" in opportunity.route else symbol_1_name[3:]
        balance = get_balance(binance_client, asset)

        if balance <= 0:
            logger.warning(f"Balance insuficiente para procesar la oportunidad: {opportunity.route}")
            return False

        # Calcular la cantidad a operar (ejemplo: 50% del balance disponible)
        quantity = balance * Decimal('0.5')

        # Ejecutar las órdenes
        buy_order = execute_order(binance_client, symbol_1_name, "BUY", quantity, price_1)
        if not buy_order:
            logger.warning(f"Fallo al ejecutar la orden de compra para symbol_1 {symbol_1_name}")
            return False

        sell_order = execute_order(binance_client, symbol_2_name.replace("_INV", ""), "SELL", quantity, price_2)
        if not sell_order:
            logger.warning(f"Fallo al ejecutar la orden de venta para symbol_2 {symbol_2_name}")
            return False

        final_order = execute_order(binance_client, symbol_3_name.replace("_INV", ""), "SELL", quantity, price_3)
        if not final_order:
            logger.warning(f"Fallo al ejecutar la orden final para symbol_3 {symbol_3_name}")
            return False

        # Registrar las transacciones
        for order, symbol_name, action, price in [
            (buy_order, symbol_1_name, "BUY", price_1),
            (sell_order, symbol_2_name, "SELL", price_2),
            (final_order, symbol_3_name, "SELL", price_3)
        ]:
            try:
                TransactionLog.objects.create(
                    opportunity=opportunity,
                    symbol=Symbol.objects.get(symbol=symbol_name),
                    action=action,
                    amount=quantity,
                    price=price,
                    fee=Decimal(order["fills"][0]["commission"]) if order.get("fills") else None,
                    timestamp=datetime.now()  # Cambiar time.now() por datetime.now()
                )
            except Exception as e:
                logger.error(f"Error al guardar el registro de transacción para {symbol_name}: {e}")

        logger.info(f"Ciclo completado exitosamente para la ruta: {opportunity.route}")
        return True

    except Exception as e:
        logger.error(f"Error al procesar oportunidad {opportunity.route}: {e}")
        return False


    
     
def get_balance(binance_client, asset):
    """
    Obtiene el balance disponible para un activo específico.

    Parámetros:
        binance_client (Client): Cliente de Binance.
        asset (str): Nombre del activo (e.g., 'BTC', 'ETH').

    Retorna:
        Decimal: Balance disponible para el activo.
    """
    try:
        account_info = binance_client.get_account()
        for balance in account_info["balances"]:
            if balance["asset"] == asset:
                return Decimal(balance["free"])
        # Si no encuentra el activo, devolver 0
        return Decimal("0")
    except Exception as e:
        logger.error(f"Error al obtener el balance para {asset}: {e}")
        return Decimal("0")

 