from django.db import models
from django.utils.timezone import now
from decimal import Decimal


class MarketPair(models.Model):
    """
    Modelo para almacenar pares de mercado, por ejemplo, BTC/USDT, ETH/BTC, etc.
    """
    base_currency = models.CharField(max_length=10)  # Moneda base (e.g., BTC)
    quote_currency = models.CharField(max_length=10)  # Moneda cotizada (e.g., USDT)
    exchange = models.CharField(max_length=50)  # Nombre del exchange (e.g., Binance)
    is_active = models.BooleanField(default=True)  # Si el par está activo

    def __str__(self):
        return f"{self.base_currency}/{self.quote_currency} - {self.exchange}"


class HistoricalPrice(models.Model):
    """
    Modelo para guardar precios históricos de los pares de mercado.
    """
    market_pair = models.ForeignKey(MarketPair, on_delete=models.CASCADE, related_name="prices")
    timestamp = models.DateTimeField(default=now)  # Momento del precio
    price = models.DecimalField(max_digits=20, decimal_places=10)  # Precio
    volume = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)  # Volumen negociado (opcional)

    class Meta:
        ordering = ['-timestamp']  # Orden por fecha, del más reciente al más antiguo
        indexes = [
            models.Index(fields=['market_pair', 'timestamp']),  # Índice para consultas rápidas
        ]

    def __str__(self):
        return f"{self.market_pair} @ {self.timestamp}: {self.price}"


class TransactionLog(models.Model):
    """
    Modelo para registrar las transacciones realizadas.
    """
    market_pair = models.ForeignKey(MarketPair, on_delete=models.SET_NULL, null=True)
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


class ArbitrageOpportunity(models.Model):
    """ 
    Modelo para almacenar información sobre cada oportunidad de arbitraje detectada.
    """
    # Par de mercado involucrados en el ciclo de arbitraje 
    pair_1 = models.ForeignKey('MarketPair', related_name='arbitrage_pair_1', on_delete=models.CASCADE)
    pair_2 = models.ForeignKey('MarketPair', related_name='arbitrage_pair_2', on_delete=models.CASCADE)
    pair_3 = models.ForeignKey('MarketPair', related_name='arbitrage_pair_3', on_delete=models.CASCADE)

    #Ruta de como se hizo el calculo y la estrategia
    route = models.CharField(max_length=200, null=True, blank=True) #Se va a guardar "BTC -> USDT -> ETH -> BTC"

    # Ganancia obtenida en el ciclo de arbitraje
    profit = models.DecimalField(max_digits=20, decimal_places=10)
    
    # Timestamp para cuándo se detectó la oportunidad
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('pair_1', 'pair_2', 'pair_3')
        indexes = [
            models.Index(fields=['pair_1', 'pair_2', 'pair_3']),
        ]

    def __str__(self):
        return f"Arbitrage: {self.pair_1} -> {self.pair_2} -> {self.pair_3} | Profit: {self.profit}"