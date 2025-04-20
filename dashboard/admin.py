from django.contrib import admin
from .models import HistoricalPrice, TradingSignal

@admin.register(HistoricalPrice)
class HistoricalPriceAdmin(admin.ModelAdmin):
    list_display = ("symbol", "close", "timestamp")
    list_filter = ("symbol",)
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)


@admin.register(TradingSignal)
class TradingSignalAdmin(admin.ModelAdmin):
    list_display = ("symbol", "signal_type", "price", "timestamp")
    list_filter = ("symbol", "signal_type")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
