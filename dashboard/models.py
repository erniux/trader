from django.db import models
from django.utils.timezone import now
from decimal import Decimal


class Symbol(models.Model):
    symbol = models.CharField(max_length=20, unique=True)
    base_asset = models.CharField(max_length=10)
    quote_asset = models.CharField(max_length=10)
    server_time = models.DateTimeField()  #servertime de la consulta timezone=UTC para conversiones futuras a tiempo local

    def __str__(self):
        return f"{self.symbol}->{self.base_asset}/{self.quote_asset}"


class HistoricalPrice(models.Model):
    """
    Modelo para guardar precios históricos de los símbolos.
    """
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE, related_name="prices")
    timestamp = models.DateTimeField(default=now)  # Momento del precio
    price = models.DecimalField(max_digits=25, decimal_places=10)  # Precio
    volume = models.DecimalField(max_digits=50, decimal_places=25, null=True, blank=True)  # Volumen negociado (opcional)

    class Meta:
        ordering = ['-timestamp']  # Orden por fecha, del más reciente al más antiguo
        indexes = [
            models.Index(fields=['symbol', 'timestamp']),  # Índice para consultas rápidas
        ]

    def __str__(self):
        return f"{self.symbol.symbol} @ {self.timestamp}: {self.price}"


class ArbitrageOpportunity(models.Model):
    """ 
    Modelo para almacenar información sobre cada oportunidad de arbitraje detectada.
    """
    # Pares de mercado involucrados en el ciclo de arbitraje (basados en Symbol)
    symbol_1 = models.ForeignKey('Symbol', related_name='arbitrage_symbol_1', on_delete=models.CASCADE)
    symbol_2 = models.ForeignKey('Symbol', related_name='arbitrage_symbol_2', on_delete=models.CASCADE)
    symbol_3 = models.ForeignKey('Symbol', related_name='arbitrage_symbol_3', on_delete=models.CASCADE)

    # Ruta del ciclo de arbitraje
    route = models.CharField(max_length=200, null=True, blank=True)  # Ejemplo: "BTC -> USDT -> ETH -> BTC"

    # Ganancia obtenida en el ciclo de arbitraje
    profit = models.DecimalField(max_digits=20, decimal_places=10)

    # Timestamp para cuándo se detectó la oportunidad
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('symbol_1', 'symbol_2', 'symbol_3', 'detected_at')
        indexes = [
            models.Index(fields=['symbol_1', 'symbol_2', 'symbol_3']),
            models.Index(fields=['detected_at']),
        ]

    def __str__(self):
        return f"Arbitrage: {self.symbol_1.symbol} -> {self.symbol_2.symbol} -> {self.symbol_3.symbol} | Profit: {self.profit}"


class TransactionLog(models.Model):
    """
    Modelo para registrar las transacciones realizadas.
    """
    opportunity = models.ForeignKey(ArbitrageOpportunity, on_delete=models.CASCADE, null=True)
    symbol = models.ForeignKey(Symbol, on_delete=models.SET_NULL, null=True)
    action = models.CharField(
        max_length=20,
        choices=[('BUY', 'Compra'), ('SELL', 'Venta')],
        default='BUY'
    )
    amount = models.DecimalField(max_digits=20, decimal_places=10)  # Cantidad negociada
    price = models.DecimalField(max_digits=20, decimal_places=10)  # Precio de ejecución
    fee = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)  # Comisión de la operación
    
    timestamp = models.DateTimeField(default=now)  # Momento de la transacción

    def __str__(self):
        return f"{self.action} {self.amount} {self.market_pair} @ {self.price}"
