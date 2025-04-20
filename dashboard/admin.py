from django.contrib import admin
from .models import HistoricalPrice, TradingSignal, BacktestRun, Trade, SimulatedTrade
from decimal import Decimal
from dashboard.backtest import run_backtest
from django.urls import path
from dashboard.admin_views.backtest_manual import backtest_manual_view
from dashboard.admin_views.equity_chart import equity_chart
from django.utils.html import format_html

@admin.register(SimulatedTrade)
class SimulatedTradeAdmin(admin.ModelAdmin):
    list_display = ("symbol", "side", "qty", "price", "total", "pnl", "ts")
    list_filter = ("symbol", "side")
    ordering = ("-ts",)

    def pnl(self, obj):
        result = obj.pnl
        if result is None:
            return "-"
        color = "green" if result > 0 else "red"
        formatted = f"{result:.2f}"
        return format_html('<span style="color: {};">{}</span>', color, formatted)


    pnl.short_description = "PnL"


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


@admin.register(BacktestRun)
class BacktestRunAdmin(admin.ModelAdmin):
    list_display = ("id", "start", "end", "initial_usd", "final_usd", "created_at", "ver_equity")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    readonly_fields = ("start", "end", "initial_usd", "final_usd", "created_at")
    search_fields = ("id",)
    actions = ["reanudar_backtest"]
    change_list_template = "admin/backtest_changelist_with_button.html"



    @admin.action(description="🔁 Volver a ejecutar Backtest seleccionado")
    def reanudar_backtest(self, request, queryset):
        from dashboard.backtest import run_backtest
        for run in queryset:
            new_run = run_backtest(
                symbol="BTCUSDT",  # por ahora estático
                start=run.start,
                end=run.end,
                initial_usd=run.initial_usd,
                fee_pct=Decimal("0.001"),
                slippage_pct=Decimal("0.001"),
                pct_take_profit=None,
                pct_stop_loss=None,
            )
            self.message_user(request, f"✔️ Backtest nuevo creado: ID {new_run.id}")

    def ver_equity(self, obj):
        return format_html(
            '<a href="/admin/equity-chart/{}/" target="_blank">📈 Ver curva</a>',
            obj.id
        )

    ver_equity.short_description = "Equity"



@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "symbol", "side", "price", "qty", "ts_fill", "pnl")
    list_filter = ("side", "symbol", "run")
    search_fields = ("symbol",)
    ordering = ("-ts_fill",)

    def pnl(self, obj):
        if obj.side != "SELL":
            return "-"
        # Buscar la operación BUY anterior de este run
        buy = Trade.objects.filter(run=obj.run, symbol=obj.symbol, side="BUY").order_by("ts_fill").last()
        if not buy:
            return "N/A"
        diff = (obj.price - buy.price) * obj.qty
        return f"{diff:.2f}"

# Agregar la URL a la vista personalizada
admin.site.get_urls = admin.site.get_urls  # evitar error si no existe

def custom_admin_urls(original_get_urls):
    def new_get_urls():
        urls = original_get_urls()
        custom = [
            path("backtest-manual/", admin.site.admin_view(backtest_manual_view), name="backtest-manual")
        ]
        return custom + urls
    return new_get_urls

admin.site.get_urls = custom_admin_urls(admin.site.get_urls)

admin.site.get_urls = admin.site.get_urls  # asegurar que exista

def add_custom_equity_chart_url(original_get_urls):
    def new_get_urls():
        urls = original_get_urls()
        custom = [
            path("equity-chart/<int:run_id>/", admin.site.admin_view(equity_chart), name="equity-chart"),
        ]
        return custom + urls
    return new_get_urls

admin.site.get_urls = add_custom_equity_chart_url(admin.site.get_urls)
