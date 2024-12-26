from django.urls import path
from dashboard.views import dashboard, get_latest_opportunities, get_balances

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('api/latest-opportunities/', get_latest_opportunities, name='latest-opportunities'),
    path('api/balances/', get_balances, name='get-balances'), 
]
