from django.shortcuts import render
from .models import ArbitrageOpportunity

def arbitrage_opportunities_list(request):
    """
    Vista para listar las oportunidades de arbitraje registradas.
    """
    opportunities = ArbitrageOpportunity.objects.all().order_by('-detected_at')
    return render(request, 'dashboard/arbitrage_opportunities_list.html', {'opportunities': opportunities})
