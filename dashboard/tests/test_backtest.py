import decimal
import numpy as np
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from dashboard.models import HistoricalPrice, TradingSignal, Trade
from dashboard.backtest import run_backtest


DEC = decimal.Decimal


class TestBacktest(TestCase):
    def setUp(self):
        self.base = timezone.now()

        prices = np.concatenate([np.arange(1, 11), np.arange(9, 0, -1)])
        for i, p in enumerate(prices):
            HistoricalPrice.objects.create(
                symbol="BTCUSDT",
                close=DEC(str(p)),
                timestamp=self.base + timedelta(minutes=i),
            )

        TradingSignal.objects.create(
            symbol="BTCUSDT",
            signal_type="BUY",
            price=DEC("3"),
            timestamp=self.base + timedelta(minutes=2),
        )
        TradingSignal.objects.create(
            symbol="BTCUSDT",
            signal_type="SELL",
            price=DEC("8"),
            timestamp=self.base + timedelta(minutes=7),
        )


    def test_pnl(self):
        start = self.base
        end = self.base + timedelta(minutes=20)
        run = run_backtest("BTCUSDT", start=start, end=end)

        self.assertEqual(run.initial_usd, DEC("1000"))

        expected_final = (DEC("1000") / DEC("3")) * DEC("8")  # 2666.666...
        self.assertEqual(run.final_usd.quantize(DEC("0.01")), expected_final.quantize(DEC("0.01")))
        self.assertGreater(run.final_usd, run.initial_usd)

    
    def test_comisiones_y_slippage(self):
        """
        Con fee/slippage de 1%, la ganancia será menor que sin comisiones.
        """
        
        start = self.base
        end = self.base + timedelta(minutes=20)

        # Ejecutamos backtest con fee y slippage
        run = run_backtest(
            symbol="BTCUSDT",
            start=start,
            end=end,
            fee_pct=DEC("0.01"),          # 1%
            slippage_pct=DEC("0.01"),     # 1%
        )

        # Ganancia bruta sin comisiones sería 2666.66...
        bruto = (DEC("1000") / DEC("3")) * DEC("8")

        print("Final con comisiones:", run.final_usd)
        self.assertLess(run.final_usd, bruto)
        self.assertGreater(run.final_usd, DEC("1000"))

    
    def test_take_profit(self):
        """
        Simula compra a 3 y que TP se ejecute al llegar a 4.5 (50% ganancia).
        """
        # Creamos nuevos precios para este test específico
        base = self.base + timedelta(hours=1)  # más tarde para no interferir

        # Precios: sube de 1 a 10 en 10 minutos
        for i, p in enumerate(range(1, 11)):
            HistoricalPrice.objects.create(
                symbol="BTCUSDT",
                close=DEC(str(p)),
                timestamp=base + timedelta(minutes=i),
            )

        # Señal de compra cuando el precio es 3 (minuto 2)
        TradingSignal.objects.create(
            symbol="BTCUSDT",
            signal_type="BUY",
            price=DEC("3"),
            timestamp=base + timedelta(minutes=2),
        )

        # Ejecutamos con TP de 50%
        run = run_backtest(
            symbol="BTCUSDT",
            start=base,
            end=base + timedelta(minutes=20),
            fee_pct=DEC("0"),              # sin fee para simplificar
            slippage_pct=DEC("0"),
            pct_take_profit=DEC("0.5"),    # 50%
        )

        # Debe vender a 4.5 (minuto 4 o 5)
        self.assertGreater(run.final_usd, DEC("1000"))
        self.assertEqual(Trade.objects.filter(run=run).count(), 2)

        sell_trade = Trade.objects.filter(run=run, side="SELL").first()
        self.assertGreaterEqual(sell_trade.price, DEC("4.5"))
