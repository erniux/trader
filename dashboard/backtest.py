import decimal
from django.utils import timezone
from dashboard.models import BacktestRun, Trade, TradingSignal, HistoricalPrice


DEC = decimal.Decimal


def run_backtest(symbol: str,
                 start=None,
                 end=None,
                 initial_usd: DEC = DEC("1000"),
                 fee_pct: DEC = DEC("0.001"),         # 0.1% comisión
                 slippage_pct: DEC = DEC("0.001"),     # 0.1% slippage
                 pct_take_profit: DEC = None,          # ej. 0.05 = 5%
                 pct_stop_loss: DEC = None,
                 qty_precision: int = 8):
    """
    Simula ejecución de señales de trading con una sola posición activa.
    Opcional: TP/SL automáticos.
    """

    equity_history = [(start, initial_usd)]  # ← Lista de tu equity en el tiempo

    start = start or timezone.make_aware(timezone.datetime.min)
    end = end or timezone.now()

    run = BacktestRun.objects.create(start=start, end=end, initial_usd=initial_usd)

    balance = initial_usd
    position_qty = DEC("0")

    signals = (TradingSignal.objects
               .filter(symbol=symbol, timestamp__gte=start, timestamp__lte=end)
               .order_by("timestamp"))

    for sig in signals:
        price = DEC(str(sig.price))

        # --- COMPRAR ---
        if sig.signal_type == "BUY" and position_qty == 0:
            slipped_price = price * (1 + slippage_pct)
            position_qty = (balance / slipped_price).quantize(DEC("1e-{}".format(qty_precision)))
            fee = position_qty * slipped_price * fee_pct
            balance = DEC("0") - fee

            Trade.objects.create(
                run=run,
                symbol=symbol,
                side="BUY",
                price=slipped_price,
                qty=position_qty,
                ts_signal=sig.timestamp,
                ts_fill=sig.timestamp,
            )
            equity_history.append((sig.timestamp, balance))


            # --- TP/SL automático (opcional) ---
            if pct_take_profit or pct_stop_loss:
                buy_price = slipped_price
                buy_ts = sig.timestamp

                take_price = buy_price * (1 + (pct_take_profit or DEC("0")))
                stop_price = buy_price * (1 - (pct_stop_loss or DEC("0")))

                future_prices = HistoricalPrice.objects.filter(
                    symbol=symbol, timestamp__gt=buy_ts
                ).order_by("timestamp")

                for p in future_prices:
                    p_price = DEC(str(p.close))
                    if p_price >= take_price or p_price <= stop_price:
                        slipped_sell = p_price * (1 - slippage_pct)
                        gross = position_qty * slipped_sell
                        fee = gross * fee_pct
                        balance = gross - fee

                        Trade.objects.create(
                            run=run,
                            symbol=symbol,
                            side="SELL",
                            price=slipped_sell,
                            qty=position_qty,
                            ts_signal=p.timestamp,
                            ts_fill=p.timestamp,
                        )
                        position_qty = DEC("0")
                        break

        # --- VENDER ---
        elif sig.signal_type == "SELL" and position_qty > 0:
            slipped_price = price * (1 - slippage_pct)
            gross = position_qty * slipped_price
            fee = gross * fee_pct
            balance = gross - fee

            Trade.objects.create(
                run=run,
                symbol=symbol,
                side="SELL",
                price=slipped_price,
                qty=position_qty,
                ts_signal=sig.timestamp,
                ts_fill=sig.timestamp,
            )
            position_qty = DEC("0")
            equity_history.append((sig.timestamp, balance))


    run.final_usd = balance
    run.save()
    return run
