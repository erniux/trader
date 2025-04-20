import decimal
import numpy as np
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from dashboard.models import HistoricalPrice, TradingSignal
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

    
