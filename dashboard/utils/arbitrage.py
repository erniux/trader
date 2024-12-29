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
from datetime import datetime


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
    

from decimal import Decimal, ROUND_DOWN

def place_buy_order(binance_client, symbol, quantity_dec, price_dec):
    symbol_info = binance_client.get_symbol_info(symbol)
    base_asset = symbol_info['baseAsset']
    quote_asset = symbol_info['quoteAsset']

    # Ejemplo de obtención de filtros
    lot_size_filter = next(
        (f for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE"), None
    )
    min_qty = Decimal(lot_size_filter["minQty"])
    max_qty = Decimal(lot_size_filter["maxQty"])
    step_size = Decimal(lot_size_filter["stepSize"])

    # 1) Revisar balance en quote_asset
    balance_quote_raw = get_balance(binance_client, quote_asset)
    balance_quote = Decimal(str(balance_quote_raw))  # Convertir a Decimal

    # 2) Calcular required_balance
    required_balance = quantity_dec * price_dec

    if required_balance > balance_quote:
        # Ajustar automáticamente la cantidad
        max_quantity = balance_quote / price_dec
        logger.warning(
            f"Balance insuficiente para BUY {symbol}. Ajustando la cantidad: "
            f"{quantity_dec} -> {max_quantity}"
        )
        quantity_dec = max_quantity

    # 3) Ajustar por step_size (ROUND_DOWN)
    quantity_dec = quantity_dec.quantize(step_size, rounding=ROUND_DOWN)

    # 4) Validar min_qty y max_qty
    if quantity_dec < min_qty:
        logger.error(
            f"La cantidad ajustada {quantity_dec} es menor que el minQty {min_qty}. Cancelando orden."
        )
        return None

    if quantity_dec > max_qty:
        logger.error(
            f"La cantidad ajustada {quantity_dec} es mayor que el maxQty {max_qty}. Cancelando orden."
        )
        return None

    # 5) Crear orden
    order = binance_client.create_order(
        symbol=symbol,
        side="BUY",
        type="LIMIT",
        timeInForce="GTC",
        quantity=float(quantity_dec),
        price=str(price_dec)
    )
    return order



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

def handle_arbitrage_opportunity(opportunity, binance_client):
    """
    Procesa una oportunidad de arbitraje específica.

    Retorna:
        bool: True si la operación fue exitosa, False en caso contrario.
    """
    try:
        # Extraer símbolos desde la ruta de la oportunidad, asumiendo formato "SYMBOL1 -> SYMBOL2 -> SYMBOL3"
        symbols = opportunity.route.split(" -> ")
        symbol_1_name = symbols[0]
        symbol_2_name = symbols[1]
        symbol_3_name = symbols[2]

        logger.info(f"Procesando oportunidad: {opportunity.route}")

        # Obtener precios y manejar _INV
        # (Si un símbolo tiene "_INV", significa que debemos tomar 1 / precio real)
        def _get_price(sym):
            is_inv = sym.endswith("_INV")
            real_sym = sym.replace("_INV", "")
            p = get_price(real_sym, binance_client)
            if p:
                return Decimal(str(1 / p)) if is_inv else Decimal(str(p))
            return None

        price_1 = _get_price(symbol_1_name)
        price_2 = _get_price(symbol_2_name)
        price_3 = _get_price(symbol_3_name)

        if not price_1 or not price_2 or not price_3:
            logger.warning(f"Precios no disponibles para la oportunidad: {opportunity.route}")
            return False

        # Determinar balance disponible en el activo base del primer símbolo
        # Ojo que la lógica "[:3]" puede fallar con DOGE, etc.
        # En la nueva versión, no hace tanta falta, porque execute_spot_order
        # hace la validación y ajuste de cantidad. Pero si deseas un
        # 'porcentaje' de tu balance, sí lo necesitas aquí.
        base_asset_1 = binance_client.get_symbol_info(symbol_1_name)["baseAsset"]
        total_balance = get_balance(binance_client, base_asset_1)
        if not total_balance or Decimal(str(total_balance)) <= 0:
            logger.warning(f"Balance insuficiente en {base_asset_1} para procesar la oportunidad.")
            return False

        # Por ejemplo, 50% de tu balance:
        quantity_dec = Decimal(str(total_balance)) * Decimal("0.5")

        # 1) Comprar el symbol_1 baseAsset al precio price_1
        #    (o si el symbol_1 es invertido, ya lo resolvimos con _get_price)
        buy_order = execute_spot_order(binance_client, symbol_1_name, "BUY", quantity_dec, price_1)
        if not buy_order:
            logger.warning(f"Fallo al ejecutar la orden de compra para {symbol_1_name}")
            return False

        # 2) Vender en el segundo símbolo
        sell_order = execute_spot_order(binance_client, symbol_2_name.replace("_INV", ""), "SELL", quantity_dec, price_2)
        if not sell_order:
            logger.warning(f"Fallo al ejecutar la orden de venta para {symbol_2_name}")
            return False

        # 3) Vender en el tercer símbolo
        final_order = execute_spot_order(binance_client, symbol_3_name.replace("_INV", ""), "SELL", quantity_dec, price_3)
        if not final_order:
            logger.warning(f"Fallo al ejecutar la orden final para {symbol_3_name}")
            return False

        # Registrar transacciones
        for order, sym_name, action, px in [
            (buy_order, symbol_1_name, "BUY", price_1),
            (sell_order, symbol_2_name, "SELL", price_2),
            (final_order, symbol_3_name, "SELL", price_3)
        ]:
            try:
                # Recuperar el objeto Symbol real (sin "_INV")
                real_sym_name = sym_name.replace("_INV", "")
                sym_obj = Symbol.objects.get(symbol=real_sym_name)
                fee = Decimal(order["fills"][0]["commission"]) if order.get("fills") else None

                TransactionLog.objects.create(
                    opportunity=opportunity,
                    symbol=sym_obj,
                    action=action,
                    amount=quantity_dec,
                    price=px,
                    fee=fee,
                    timestamp=datetime.now() 
                )
            except Exception as e:
                logger.error(f"Error al guardar el registro de transacción para {sym_name}: {e}")

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


def execute_spot_order(binance_client, symbol, side, quantity, price=None):
    """
    Ejecuta una orden spot en Binance (BUY o SELL) para un símbolo específico, 
    ajustando la cantidad y el precio a los requisitos de los filtros.

    Parámetros:
        binance_client (Client): Cliente de Binance (python-binance u otro).
        symbol (str): Símbolo del par. Ej: 'BNBUSDT', 'ETHUSDT', etc.
        side (str): 'BUY' o 'SELL'.
        quantity (Decimal): Cantidad deseada en términos del baseAsset.
        price (Decimal, opcional): Precio límite. Si es None, la orden será de mercado.

    Retorna:
        dict | None: Diccionario con la respuesta de la API de Binance si se crea la orden,
                     o None si hubo algún fallo en la validación de filtros o en la creación.
    """
    try:
        # 1. Obtener información del símbolo
        symbol_info = binance_client.get_symbol_info(symbol)
        if not symbol_info:
            logger.error(f"No se encontró información para el símbolo {symbol}")
            return None

        base_asset = symbol_info["baseAsset"]
        quote_asset = symbol_info["quoteAsset"]

        # 2. Extraer filtros relevantes
        lot_size_filter = next(
            (f for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE"), 
            None
        )
        price_filter = next(
            (f for f in symbol_info["filters"] if f["filterType"] == "PRICE_FILTER"), 
            None
        )
        min_notional_filter = next(
            (f for f in symbol_info["filters"] if f["filterType"] == "MIN_NOTIONAL"), 
            None
        )

        if not lot_size_filter:
            logger.error(f"No se encontró el filtro LOT_SIZE para {symbol}")
            return None

        # 3. Parsear valores LOT_SIZE
        min_qty = Decimal(lot_size_filter["minQty"])     # Cantidad mínima
        max_qty = Decimal(lot_size_filter["maxQty"])     # Cantidad máxima
        step_size = Decimal(lot_size_filter["stepSize"]) # Incremento mínimo

        logger.debug(
            f"[execute_spot_order] LOT_SIZE => minQty={min_qty}, maxQty={max_qty}, stepSize={step_size}"
        )

        # 4. Obtener balance según BUY/SELL
        #    SELL => necesito balance del baseAsset
        #    BUY  => necesito balance del quoteAsset para pagar
        if side.upper() == "SELL":
            balance_raw = get_balance(binance_client, base_asset)
            if balance_raw is None:
                logger.error(f"No se pudo obtener balance de {base_asset}")
                return None
            balance_dec = Decimal(str(balance_raw))
            required_balance = quantity  # vendes 'quantity' unidades del baseAsset
            logger.debug(f"Balance baseAsset({base_asset})={balance_dec}, required_balance={required_balance}")

            if required_balance > balance_dec:
                # Ajustar la cantidad a la máxima posible
                logger.warning(
                    f"Balance insuficiente para SELL {symbol}. Ajustando la cantidad "
                    f"de {quantity} -> {balance_dec}"
                )
                quantity = balance_dec

        else:  # BUY
            balance_raw = get_balance(binance_client, quote_asset)
            if balance_raw is None:
                logger.error(f"No se pudo obtener balance de {quote_asset}")
                return None
            balance_dec = Decimal(str(balance_raw))

            # Si price es None => orden MARKET (difícil saber la cantidad exacta que se ejecuta)
            if price is None:
                # Podrías asumir que gastarás todo tu balance, o
                # un porcentaje, según tu lógica. Aquí damos por hecho
                # que 'quantity' ya está calculado de otra forma.
                required_balance = quantity  # No es exacto para MARKET, pero hacemos un check mínimo
            else:
                required_balance = quantity * price

            logger.debug(f"Balance quoteAsset({quote_asset})={balance_dec}, required_balance={required_balance}")

            if required_balance > balance_dec:
                # Ajustar la cantidad máxima
                if price and price > 0:
                    max_quantity = balance_dec / price
                else:
                    max_quantity = Decimal("0")  # Evita division by zero

                logger.warning(
                    f"Balance insuficiente para BUY {symbol}. Ajustando la cantidad: "
                    f"{quantity} -> {max_quantity}"
                )
                quantity = max_quantity

        # 5. Ajustar la cantidad a stepSize con ROUND_DOWN
        quantity_before_quantize = quantity
        quantity = quantity.quantize(step_size, rounding=ROUND_DOWN)

        logger.debug(
            f"Cantidad antes de quantize={quantity_before_quantize} / "
            f"después de quantize={quantity} con stepSize={step_size}"
        )

        # 6. Validar minQty y maxQty
        if quantity < min_qty:
            logger.error(
                f"La cantidad ajustada {quantity} es menor que minQty {min_qty} para {symbol}. Orden cancelada."
            )
            return None
        if quantity > max_qty:
            logger.error(
                f"La cantidad ajustada {quantity} excede maxQty {max_qty} para {symbol}. Orden cancelada."
            )
            return None

        # 7. Validar PRICE_FILTER (si es orden LIMIT y se definió 'price')
        #    Evita Filter failure: PRICE_FILTER
        if price_filter and price is not None:
            min_price = Decimal(price_filter["minPrice"])
            max_price = Decimal(price_filter["maxPrice"])
            tick_size = Decimal(price_filter["tickSize"])

            # Ajustar el precio al tickSize
            price_before_quantize = price
            price = price.quantize(tick_size, rounding=ROUND_DOWN)

            logger.debug(
                f"Precio antes de quantize={price_before_quantize}, "
                f"después de quantize={price}, tickSize={tick_size}"
            )

            if price < min_price or price > max_price:
                logger.error(
                    f"El precio {price} está fuera del rango [{min_price}, {max_price}] para {symbol}."
                )
                return None

        # 8. Validar MIN_NOTIONAL (si aplica)
        #    minNotional se refiere a la cantidad * price en la quoteAsset.
        if min_notional_filter and price is not None and quantity > 0:
            min_notional = Decimal(min_notional_filter["minNotional"])
            notional = (quantity * price) if side.upper() == "BUY" else (quantity * price)
            # Para SELL es igual: la "compra" inversa en la quote.

            if notional < min_notional:
                logger.error(
                    f"El notional {notional} es menor que minNotional {min_notional} para {symbol}."
                )
                return None

        # 9. Crear la orden
        #    - Para LIMIT => pasamos 'price'.
        #    - Para MARKET => omitimos 'price'.
        #    - quantity como string para evitar flotantes binarios.

        logger.info("=== [ORDEN SPOT] ===")
        logger.info(f"Simbolo: {symbol}")
        logger.info(f"side: {side.upper()}")
        logger.info(f"Cantidad calculada (antes de quantize): {quantity_before_quantize}")
        logger.info(f"Cantidad final (despues de quantize): {quantity}")
        logger.info(f"minQty={min_qty}, maxQty={max_qty}, stepSize={step_size}")
        logger.info(f"price_filter={price_filter}, min_notional_filter={min_notional_filter}")
        if price is not None:
            logger.info(f"Precio final={price}")
        if min_notional_filter and price is not None:
            min_notional = Decimal(min_notional_filter["minNotional"])
            notional = quantity * price
            logger.info(f"notional={notional}, minNotional={min_notional}")
        logger.info("====================")



        try:
            if price and side.upper() in ["BUY", "SELL"]:
                # Orden LIMIT
                order = binance_client.create_order(
                    symbol=symbol,
                    side=side.upper(),
                    type="LIMIT",
                    timeInForce="GTC",
                    quantity=str(quantity),
                    price=str(price)
                )
            else:
                # Orden MARKET
                order = binance_client.create_order(
                    symbol=symbol,
                    side=side.upper(),
                    type="MARKET",
                    quantity=str(quantity),
                )
            logger.info(f"[execute_spot_order] Orden creada exitosamente: {order}")
            return order

        except Exception as api_error:
            logger.error(f"Error al ejecutar la orden {side} para {symbol}: {api_error}")
            return None

    except Exception as e:
        logger.error(f"Error inesperado en execute_spot_order para {symbol}: {e}")
        return None