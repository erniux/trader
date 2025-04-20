from django import forms
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import admin, messages
from decimal import Decimal
from dashboard.backtest import run_backtest
from dashboard.models import BacktestRun
from django.utils import timezone


class BacktestManualForm(forms.Form):
    symbol = forms.CharField(label="Símbolo", initial="BTCUSDT")
    fee = forms.DecimalField(label="Fee %", initial=Decimal("0.001"))
    slippage = forms.DecimalField(label="Slippage %", initial=Decimal("0.001"))
    tp = forms.DecimalField(label="Take-Profit %", required=False)
    sl = forms.DecimalField(label="Stop-Loss %", required=False)


def backtest_manual_view(request):
    if request.method == "POST":
        form = BacktestManualForm(request.POST)
        if form.is_valid():
            symbol = form.cleaned_data["symbol"]
            fee = form.cleaned_data["fee"]
            slippage = form.cleaned_data["slippage"]
            tp = form.cleaned_data["tp"]
            sl = form.cleaned_data["sl"]

            now = timezone.now()
            start = now - timezone.timedelta(hours=2)

            run = run_backtest(
                symbol=symbol,
                start=start,
                end=now,
                fee_pct=fee,
                slippage_pct=slippage,
                pct_take_profit=tp,
                pct_stop_loss=sl,
            )
            messages.success(request, f"✅ Backtest creado: ID {run.id} - Resultado: {run.final_usd} USD")
            return redirect("admin:dashboard_backtestrun_changelist")
    else:
        form = BacktestManualForm()

    return render(request, "admin/backtest_manual.html", {"form": form})
