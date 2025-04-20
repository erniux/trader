import decimal
from django.utils import timezone
from dashboard.models import BacktestRun, Trade, TradingSignal


DEC = decimal.Decimal

def run_backtest(symbol: str,
                 start=None,
                 end=None,
                 initial_usd: decimal.Decimal = DEC("1000"),
                 qty_precision: int = 8):
    """
    Recorre señales BUY/SELL y simula una única posición a la vez.
    """
    start = start or timezone.make_aware(timezone.datetime.min)
    end   = end   or timezone.now()

    run = BacktestRun.objects.create(start=start, end=end, initial_usd=initial_usd)

    balance = initial_usd
    position_qty = DEC("0")

    signals = (TradingSignal.objects.filter(symbol=symbol,
                                            timestamp__gte=start,
                                            timestamp__lte=end)
               .order_by("timestamp"))

    for sig in signals:
        price = DEC(sig.price)
        if sig.signal_type == "BUY" and position_qty == 0:
            # comprar con todo el balance
            position_qty = (balance / price).quantize(DEC("1e-{}".format(qty_precision)))
            balance = DEC("0")
            Trade.objects.create(run=run, symbol=symbol, side="BUY",
                                 price=price, qty=position_qty,
                                 ts_signal=sig.timestamp, ts_fill=sig.timestamp)
        elif sig.signal_type == "SELL" and position_qty > 0:
            # vender toda la posición
            balance = position_qty * price
            Trade.objects.create(run=run, symbol=symbol, side="SELL",
                                 price=price, qty=position_qty,
                                 ts_signal=sig.timestamp, ts_fill=sig.timestamp)
            position_qty = DEC("0")

    print(signals.count(), signals.first().timestamp, signals.last().timestamp)

    run.final_usd = balance
    run.save()
    return run
