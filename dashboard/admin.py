from django.contrib import admin
from .models import MarketPair, HistoricalPrice, TransactionLog, ArbitrageOpportunity


@admin.register(MarketPair)
class MarketPairAdmin(admin.ModelAdmin):
    list_display = ('base_currency', 'quote_currency', 'exchange', 'is_active')
    search_fields = ('base_currency', 'quote_currency', 'exchange')
    list_filter = ('exchange', 'is_active')


@admin.register(HistoricalPrice)
class HistoricalPriceAdmin(admin.ModelAdmin):
    list_display = ('market_pair', 'timestamp', 'price', 'volume')
    search_fields = ('market_pair__base_currency', 'market_pair__quote_currency')
    list_filter = ('market_pair',)
    date_hierarchy = 'timestamp'


@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ('market_pair', 'action', 'amount', 'price', 'fee', 'timestamp')
    search_fields = ('market_pair__base_currency', 'market_pair__quote_currency', 'action')
    list_filter = ('action', 'market_pair')
    date_hierarchy = 'timestamp'


@admin.register(ArbitrageOpportunity)
class ArbitrageOpportunityAdmin(admin.ModelAdmin):
    list_display = ("pair_1", "pair_2", "pair_3", "route", "profit")
    search_filter = ("pair_1", "pair_2", "pair_3","profit")
    list_filter = ("route",)
    date_hierarchy = 'detected_at'
