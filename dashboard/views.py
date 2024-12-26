import os
from django.shortcuts import render
from .models import ArbitrageOpportunity
from django.http import JsonResponse
from dashboard.models import ArbitrageOpportunity
from django.http import JsonResponse
from decimal import Decimal
from .utils.arbitrage import get_balance  
from binance.client import Client


# Configuración de la API de Binance Testnet
BINANCE_TESTNET_API_KEY = os.getenv('BINANCE_TESTNET_API_KEY')
BINANCE_TESTNET_API_SECRET = os.getenv('BINANCE_TESTNET_API_SECRET')
TESTNET_BASE_URL = os.getenv('TESTNET_BASE_URL')  # URL del Testnet

# Cliente configurado para el entorno de pruebas
client = Client(BINANCE_TESTNET_API_KEY, BINANCE_TESTNET_API_SECRET)
client.API_URL = TESTNET_BASE_URL

def dashboard(request):
    """
    Vista para listar las oportunidades de arbitraje registradas.
    """
    opportunities = ArbitrageOpportunity.objects.all().order_by('-detected_at')[:10]
    return render(request, 'dashboard/dashboard.html', {'opportunities': opportunities})


def get_latest_opportunities(request):
    """
    Devuelve las últimas oportunidades de arbitraje en formato JSON.
    """
    opportunities = ArbitrageOpportunity.objects.order_by('-detected_at')[:10]
    data = [
        {
            'route': opp.route,
            'profit': float(opp.profit),
            'detected_at': opp.detected_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
        for opp in opportunities
    ]
    return JsonResponse({'opportunities': data})


def get_balances(request):
    """
    Devuelve los balances actuales de todos los activos en formato JSON.
    """
    try:
        account_info = client.get_account()
        balances = [
            {
                'asset': balance['asset'],
                'free': float(balance['free']),
                'locked': float(balance['locked']),
            }
            for balance in account_info['balances']
            if Decimal(balance['free']) > 0 or Decimal(balance['locked']) > 0  # Solo mostrar balances positivos
        ]
        return JsonResponse({'balances': balances})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)