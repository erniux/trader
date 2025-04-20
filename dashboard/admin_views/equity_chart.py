import matplotlib.pyplot as plt
from io import BytesIO
from django.http import HttpResponse
from dashboard.models import Trade, BacktestRun


def equity_chart(request, run_id):
    run = BacktestRun.objects.get(id=run_id)
    trades = Trade.objects.filter(run=run).order_by("ts_fill")

    balance = run.initial_usd
    qty = 0
    timestamps = [run.start]
    balances = [balance]

    for trade in trades:
        if trade.side == "BUY":
            qty = trade.qty
            balance = 0
        elif trade.side == "SELL":
            balance = trade.price * qty
            qty = 0
        timestamps.append(trade.ts_fill)
        balances.append(balance)

    plt.figure(figsize=(10, 4))
    plt.plot(timestamps, balances, marker="o")
    plt.xlabel("Tiempo")
    plt.ylabel("Balance (USD)")
    plt.title(f"Curva de equity - Run #{run.id}")
    plt.grid(True)
    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type="image/png")
