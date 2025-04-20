import numpy as np
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from dashboard.models import HistoricalPrice, TradingSignal
from dashboard.tasks import detectar_ma_cross


class TestDeteccionMaCross(TestCase):
    def setUp(self):
        base_ts = timezone.now()

        prices = np.array([
            1,2,3,4,5,6,7,8,9,10,
            11,12,13,14,15,16,17,16,15,14,
            13,12,11,10,9,8,7,6,5,4
        ], dtype=float)

        for i, p in enumerate(prices):
            HistoricalPrice.objects.create(
                symbol="BTCUSDT",
                close=p,
                timestamp=base_ts + timedelta(minutes=i)
            )

    def test_task_crea_signales(self):
        # Ejecuta la tarea sin broker (sincronamente)
        res = detectar_ma_cross.apply(args=["BTCUSDT", 3, 5]).get()

        assert res["created"] == 2
        assert TradingSignal.objects.filter(symbol="BTCUSDT",
                                            signal_type="BUY").count() == 1
        assert TradingSignal.objects.filter(symbol="BTCUSDT",
                                            signal_type="SELL").count() == 1
