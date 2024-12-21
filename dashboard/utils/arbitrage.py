# dashboard/utils/arbitrage.py

from decimal import Decimal
from collections import defaultdict
import logging

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
        step2 = step1_final * price_b
        step2_after_fee = step2 * (Decimal('1') - fee_rate)
        step2_final = step2_after_fee * (Decimal('1') - slippage_rate)

        # Paso 3: Convertir pair3.base -> pair3.quote (final)
        step3 = step2_final * price_c
        step3_after_fee = step3 * (Decimal('1') - fee_rate)
        final_amount = step3_after_fee * (Decimal('1') - slippage_rate)

        # Calcular la ganancia
        profit = final_amount - initial_amount
        logger.warning(f"price_a::: {price_a}, price_b::: {price_b}, price_c ::: {price_c}")
        logger.warning(f"---> initial_amount ---> {initial_amount}")
        logger.warning(f"---> final_amount ---> {final_amount}")
        logger.warning(f"---> PROFIT!!!!!! ---> {profit}")


        return profit

    except Exception as e:
        logger.error(f"Error al calcular la ganancia de arbitraje: {e}")
        return Decimal('0')


def find_arbitrage_routes(market_pairs):
    """
    Encuentra todas las rutas posibles de arbitraje triangular.

    Parámetros:
        market_pairs (QuerySet): QuerySet de MarketPair disponibles.

    Retorna:
        List[List[MarketPair]]: Lista de rutas, donde cada ruta es una lista de tres MarketPair.
    """
    # Construir el grafo
    graph = defaultdict(list)
    for pair in market_pairs:
        graph[pair.base_currency].append(pair.quote_currency)
    
    routes = []
    visited = set()

    # Buscar triángulos en el grafo
    for start in graph:
        for intermediate in graph[start]:
            if intermediate == start:
                continue
            for end in graph[intermediate]:
                if end == intermediate or end == start:
                    continue
                if start in graph[end]:
                    # Encontramos un triángulo: start -> intermediate -> end -> start
                    # Ahora, obtener los MarketPair correspondientes
                    try:
                        pair1 = market_pairs.get(base_currency=start, quote_currency=intermediate)
                        pair2 = market_pairs.get(base_currency=intermediate, quote_currency=end)
                        pair3 = market_pairs.get(base_currency=end, quote_currency=start)
                        route = [pair1, pair2, pair3]
                        # Evitar rutas duplicadas (independientemente del orden)
                        route_ids = tuple(sorted([pair1.id, pair2.id, pair3.id]))
                        if route_ids not in visited:
                            routes.append(route)
                            visited.add(route_ids)
                    except Exception as e:
                        continue
    return routes