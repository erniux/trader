from django.contrib import admin
from .models import HistoricalPrice, TransactionLog, ArbitrageOpportunity, Symbol


@admin.register(HistoricalPrice)
class HistoricalPriceAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'price', 'volume', 'timestamp')
    list_filter = ('symbol', 'timestamp')
    search_fields = ('symbol__symbol',)


@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'amount', 'action', 'price', 'timestamp')  
    list_filter = ('symbol', 'action', 'timestamp')  
    search_fields = ('symbol__symbol',)


@admin.register(ArbitrageOpportunity)
class ArbitrageOpportunityAdmin(admin.ModelAdmin):
    list_display = ('symbol_1', 'symbol_2', 'symbol_3', 'profit', 'detected_at')
    list_filter = ('symbol_1', 'symbol_2', 'symbol_3', 'detected_at')
    search_fields = ('symbol_1__symbol', 'symbol_2__symbol', 'symbol_3__symbol')
    date_hierarchy = 'detected_at'


@admin.register(Symbol)
class SymbolAdmin(admin.ModelAdmin):
    list_display = ("symbol", "base_asset", "quote_asset", "server_time")
    search_filter = ("symbol", "base_asset", "quote_asset")
    list_filter = ("symbol", "base_asset",)
    date_hierarchy = 'server_time'

 
