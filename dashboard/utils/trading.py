from dashboard.models import SimulatedTrade
from decimal import Decimal

def get_last_buy(symbol):
    return SimulatedTrade.objects.filter(symbol=symbol, side="BUY").order_by("-ts").first()

def is_holding(symbol):
    """
    Devuelve True si existe una BUY sin su SELL correspondiente.
    """
    buys = SimulatedTrade.objects.filter(symbol=symbol, side="BUY").count()
    sells = SimulatedTrade.objects.filter(symbol=symbol, side="SELL").count()
    return buys > sells
