from django.core.management.base import BaseCommand
from dashboard.backtest import run_backtest
from decimal import Decimal
from django.utils import timezone


class Command(BaseCommand):
    help = "Ejecuta un backtest manual para un símbolo dado"

    def add_arguments(self, parser):
        parser.add_argument("--symbol", type=str, default="BTCUSDT")
        parser.add_argument("--fee", type=str, default="0.001")
        parser.add_argument("--slip", type=str, default="0.001")
        parser.add_argument("--tp", type=str, default=None)
        parser.add_argument("--sl", type=str, default=None)

    def handle(self, *args, **options):
        symbol = options["symbol"]
        fee = Decimal(options["fee"])
        slip = Decimal(options["slip"])
        tp = Decimal(options["tp"]) if options["tp"] else None
        sl = Decimal(options["sl"]) if options["sl"] else None

        end = timezone.now()
        start = end - timezone.timedelta(hours=2)

        run = run_backtest(
            symbol=symbol,
            start=start,
            end=end,
            fee_pct=fee,
            slippage_pct=slip,
            pct_take_profit=tp,
            pct_stop_loss=sl,
        )

        self.stdout.write(self.style.SUCCESS(
            f"✅ Backtest completado. Inicial: {run.initial_usd}, Final: {run.final_usd} USD"
        ))
