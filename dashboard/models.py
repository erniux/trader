from django.db import models
from django.utils import timezone
from decimal import Decimal


class HistoricalPrice(models.Model):
    """
    Precio OHLCV (o solo 'close') por símbolo y timestamp.
    Guarda los datos que alimentarán los indicadores.
    """
    symbol = models.CharField(max_length=20)
    close = models.DecimalField(max_digits=20, decimal_places=8)
    timestamp = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["symbol", "timestamp"]
        unique_together = ("symbol", "timestamp")

    def __str__(self):
        return f"{self.symbol} @ {self.timestamp:%Y-%m-%d %H:%M} → {self.close}"


class TradingSignal(models.Model):
    """
    Resultado de la tarea: BUY o SELL detectado por cruce de medias.
    """
    BUY = "BUY"
    SELL = "SELL"
    TYPES = [(BUY, "Compra"), (SELL, "Venta")]

    symbol = models.CharField(max_length=20)
    signal_type = models.CharField(max_length=4, choices=TYPES)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    timestamp = models.DateTimeField(db_index=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        unique_together = ("symbol", "timestamp", "signal_type")

    def __str__(self):
        return f"{self.symbol} {self.signal_type} @ {self.timestamp:%Y-%m-%d %H:%M}"


class BacktestRun(models.Model):
    start = models.DateTimeField()
    end   = models.DateTimeField()
    initial_usd = models.DecimalField(max_digits=20, decimal_places=8)
    final_usd   = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

class Trade(models.Model):
    BUY = "BUY"; SELL = "SELL"
    run   = models.ForeignKey(BacktestRun, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=20)
    side   = models.CharField(max_length=4, choices=[(BUY,"BUY"),(SELL,"SELL")])
    price  = models.DecimalField(max_digits=20, decimal_places=8)
    qty    = models.DecimalField(max_digits=20, decimal_places=8)
    ts_signal = models.DateTimeField()
    ts_fill   = models.DateTimeField()


class Wallet(models.Model):
    symbol = models.CharField(max_length=20, default="USDT")
    balance = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("1000"))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.symbol}: {self.balance}"
    
class SimulatedTrade(models.Model):
    BUY = "BUY"
    SELL = "SELL"
    SIDE_CHOICES = [(BUY, "Buy"), (SELL, "Sell")]

    symbol = models.CharField(max_length=20)
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    qty = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    total = models.DecimalField(max_digits=20, decimal_places=8)
    ts = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ts} | {self.side} {self.qty} {self.symbol} @ {self.price}"

    @property
    def pnl(self):
        """
        Retorna la ganancia/pérdida si esta es una operación SELL.
        Se calcula como: (precio de venta - precio de compra) * cantidad
        """
        if self.side != "SELL":
            return None
        # Buscar la última compra antes de esta venta
        from dashboard.models import SimulatedTrade
        last_buy = (
            SimulatedTrade.objects
            .filter(symbol=self.symbol, side="BUY", ts__lt=self.ts)
            .order_by("-ts")
            .first()
        )
        if not last_buy:
            return None
        return (self.price - last_buy.price) * self.qty


    