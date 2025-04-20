import numpy as np
from datetime import datetime, timezone
from celery import shared_task
from django.db import transaction
from decimal import Decimal

from dashboard.models import HistoricalPrice, TradingSignal, Wallet, SimulatedTrade
from core.analysis.indicators import ma_cross_signals, rsi
from dashboard.utils.binance_service import fetch_last_candles
from dashboard.utils.redis_service import get_live_price
from dashboard.utils.trading import is_holding, get_last_buy



@shared_task
def load_recent_prices(symbol: str, lookback: int = 1000):
    """Download the latest `lookback` 1‑min candles for `symbol` and
    persist them in HistoricalPrice if they do not already exist."""
    candles = fetch_last_candles(symbol, limit=lookback)
    created = 0
    for close_price, close_time_s in candles:
        ts = datetime.fromtimestamp(close_time_s, tz=timezone.utc)
        _, was_created = HistoricalPrice.objects.get_or_create(
            symbol=symbol,
            timestamp=ts,
            defaults={"close": close_price},
        )
        if was_created:
            created += 1
    return {"created": created}


@shared_task
def detectar_ma_cross(symbol: str, short: int = 5, long: int = 20):
    qs = (HistoricalPrice.objects
          .filter(symbol=symbol)
          .order_by("timestamp")
          .values_list("close", "timestamp"))

    if not qs.exists():
        return {"created": 0}

    closes, timestamps = zip(*qs)
    closes = np.array(closes, dtype=float)

    signals = ma_cross_signals(closes, short=short, long=long)

    created = 0
    with transaction.atomic():
        for kind, idxs in signals.items():
            for i in idxs:
                ts = timestamps[i]
                price = closes[i]
                _, was_created = TradingSignal.objects.get_or_create(
                    symbol=symbol,
                    signal_type=kind,
                    timestamp=ts,
                    defaults={
                        "price": price,
                        "meta": {"short": short, "long": long},
                    },
                )
                if was_created:
                    created += 1
    return {"created": created}


@shared_task
def detectar_rsi_extremos(symbol: str, period: int = 14, low: float = 30.0, high: float = 70.0):
    """Evaluates RSI on the latest price series and creates TradingSignal rows
    when RSI crosses below `low` (BUY) or above `high` (SELL)."""
    qs = (HistoricalPrice.objects
          .filter(symbol=symbol)
          .order_by("timestamp")
          .values_list("close", "timestamp"))

    if qs.count() <= period:
        return {"created": 0}

    closes, timestamps = zip(*qs)
    closes = np.array(closes, dtype=float)

    rsi_vals = rsi(closes, period=period)

    buy_idx = np.where((rsi_vals[:-1] >= low) & (rsi_vals[1:] < low))[0] + 1
    sell_idx = np.where((rsi_vals[:-1] <= high) & (rsi_vals[1:] > high))[0] + 1

    created = 0
    with transaction.atomic():
        for idx in buy_idx.tolist():
            ts = timestamps[idx]
            price = closes[idx]
            _, was_created = TradingSignal.objects.get_or_create(
                symbol=symbol,
                signal_type="BUY",
                timestamp=ts,
                defaults={
                    "price": price,
                    "meta": {"indicator": "RSI", "period": period, "value": float(rsi_vals[idx])},
                },
            )
            if was_created:
                created += 1

        for idx in sell_idx.tolist():
            ts = timestamps[idx]
            price = closes[idx]
            _, was_created = TradingSignal.objects.get_or_create(
                symbol=symbol,
                signal_type="SELL",
                timestamp=ts,
                defaults={
                    "price": price,
                    "meta": {"indicator": "RSI", "period": period, "value": float(rsi_vals[idx])},
                },
            )
            if was_created:
                created += 1

    return {"created": created}

# ────────────────────────────────────────────────
#  TASK: SIMULAR COMPRA 
# ────────────────────────────────────────────────

@shared_task
def simular_compra(symbol="BTCUSDT", qty=Decimal("0.001")):
    qty = Decimal(str(qty))
    price = get_live_price(symbol)
    if not price:
        return "❌ Precio no disponible"

    wallet, _ = Wallet.objects.get_or_create(symbol="USDT")
    price = Decimal(price)
    total = qty * price

    if wallet.balance < total:
        return "❌ Saldo insuficiente"

    wallet.balance -= total
    wallet.save()

    SimulatedTrade.objects.create(
        symbol=symbol,
        side="BUY",
        qty=qty,
        price=price,
        total=total,
    )

    return f"✅ Compra simulada: {qty} {symbol} a {price} USDT"


# ────────────────────────────────────────────────
#  TASK: SIMULAR VENTA
# ────────────────────────────────────────────────

@shared_task
def simular_venta(symbol="BTCUSDT", qty=Decimal("0.001")):
    qty = Decimal(str(qty))
    price = get_live_price(symbol)
    if not price:
        return "❌ Precio no disponible"

    wallet, _ = Wallet.objects.get_or_create(symbol="USDT")
    price = Decimal(price)
    total = qty * price

    wallet.balance += total
    wallet.save()

    SimulatedTrade.objects.create(
        symbol=symbol,
        side="SELL",
        qty=qty,
        price=price,
        total=total,
    )

    return f"✅ Venta simulada: {qty} {symbol} a {price} USDT"



@shared_task
def ejecutar_ordenes_por_senal(symbol="BTCUSDT"):
    """
    Lee la última señal y ejecuta compra/venta simulada si se cumplen condiciones.
    """
    last_signal = TradingSignal.objects.filter(symbol=symbol).order_by("-timestamp").first()
    if not last_signal:
        return "❌ Sin señales"

    price = get_live_price(symbol)
    if not price:
        return "❌ Precio no disponible"

    qty = Decimal("0.0002")  # ajustar según saldo

    if last_signal.signal_type == "BUY":
        if not is_holding(symbol):
            return simular_compra(symbol=symbol, qty=qty)
        else:
            return "🟡 Ya tengo posición, no compro"

    if last_signal.signal_type == "SELL":
        if is_holding(symbol):
            buy = get_last_buy(symbol)
            price = Decimal(price)
            if price > buy.price:  # 💰 vendemos solo si hay ganancia
                return simular_venta(symbol=symbol, qty=qty)
            else:
                return "⛔ No vendo, aún no hay ganancia"
        else:
            return "🟡 No tengo posición abierta, no vendo"
